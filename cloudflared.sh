#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "${1:-start}" in
  start|stop|urls|apply) exec .venv/bin/python scripts/services.py "tunnels-${1:-start}" ;;
  *) echo 'Usage: bash cloudflared.sh {start|stop|urls|apply}' >&2; exit 1 ;;
esac
