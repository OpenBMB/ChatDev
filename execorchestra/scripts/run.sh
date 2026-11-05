#!/usr/bin/env bash
set -euo pipefail
exec_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$exec_root"
export PYTHONPATH="$exec_root"
exec "${SGAR_PYTHON:-python}" -m sgar_mvp.main --config "${SGAR_CONFIG:-$exec_root/sgar_mvp/config.json}" "$@"
