#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_PID_FILE="$STATE_DIR/backend.pid"
FRONTEND_PID_FILE="$STATE_DIR/frontend.pid"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-6400}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"

mkdir -p "$STATE_DIR" "$LOG_DIR"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

cleanup() {
  if [ -f "$FRONTEND_PID_FILE" ]; then
    local frontend_pid
    frontend_pid="$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)"
    if [ -n "${frontend_pid:-}" ] && kill -0 "$frontend_pid" 2>/dev/null; then
      kill "$frontend_pid" 2>/dev/null || true
    fi
    rm -f "$FRONTEND_PID_FILE"
  fi

  if [ -f "$BACKEND_PID_FILE" ]; then
    local backend_pid
    backend_pid="$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)"
    if [ -n "${backend_pid:-}" ] && kill -0 "$backend_pid" 2>/dev/null; then
      kill "$backend_pid" 2>/dev/null || true
    fi
    rm -f "$BACKEND_PID_FILE"
  fi
}

trap cleanup EXIT INT TERM

require_command uv
require_command node
require_command npm

bash "$ROOT_DIR/scripts/stop.sh" >/dev/null 2>&1 || true

BACKEND_ARGS=(run python server_main.py --host "$BACKEND_HOST" --port "$BACKEND_PORT")
if [ "$BACKEND_RELOAD" = "1" ]; then
  BACKEND_ARGS+=(--reload)
fi

(
  cd "$ROOT_DIR"
  uv "${BACKEND_ARGS[@]}"
) >"$LOG_DIR/dev-backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" >"$BACKEND_PID_FILE"

(
  cd "$ROOT_DIR/frontend"
  VITE_API_BASE_URL="http://$BACKEND_HOST:$BACKEND_PORT" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) >"$LOG_DIR/dev-frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >"$FRONTEND_PID_FILE"

echo "MovieDev dev environment is starting..."
echo "Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "Logs:"
echo "  $LOG_DIR/dev-backend.log"
echo "  $LOG_DIR/dev-frontend.log"
echo "Press Ctrl+C to stop both services."

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend process exited unexpectedly. Check $LOG_DIR/dev-backend.log"
    exit 1
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Frontend process exited unexpectedly. Check $LOG_DIR/dev-frontend.log"
    exit 1
  fi
  sleep 2
done
