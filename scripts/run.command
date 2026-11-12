#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VENV="$HOME/.cache/echo-chamber/venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  candidates=("${ECR_PYTHON:-}" "$(command -v python3.12 || true)" "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" "$(command -v python3 || true)")
  found=""
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" ]] && "$candidate" -c 'import sys; assert sys.version_info >= (3,12)' 2>/dev/null; then
      found="$candidate"
      break
    fi
  done
  if [[ -z "$found" ]]; then
    echo "需要 Python 3.12 或更新版本；安装后重试，或设置 ECR_PYTHON。"
    exit 1
  fi
  "$found" -m venv "$VENV"
fi
if ! cmp -s requirements.txt "$VENV/.echo-requirements.txt"; then
  "$VENV/bin/python" -m pip install -r requirements.txt
  cp requirements.txt "$VENV/.echo-requirements.txt"
fi
export PYTHONPYCACHEPREFIX="$HOME/.cache/echo-chamber/pycache"
export NUMBA_CACHE_DIR="$HOME/.cache/echo-chamber/numba"
unset PYTHONPATH
exec "$VENV/bin/python" -u -m echo "$@"
