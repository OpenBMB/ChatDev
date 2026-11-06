#!/usr/bin/env bash
set -euo pipefail

exec_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$exec_root"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

exec "${SGAR_PYTHON:-python}" -m scripts.run_xbench_demo
