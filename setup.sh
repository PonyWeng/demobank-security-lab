#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != "Linux" ]]; then
  echo 'Run setup.sh on Ubuntu/Linux. Windows: use python scripts/bootstrap.py after installing requirements.' >&2
  exit 1
fi
if [[ "$(id -u)" == 0 ]]; then
  echo 'Run as your normal VM user (bash setup.sh), not sudo bash setup.sh.' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1 || ! python3 -m venv --help >/dev/null 2>&1 || ! dpkg-query -W -f='${Status}' python3-venv 2>/dev/null | grep -q 'install ok installed'; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv
fi
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/bootstrap.py
.venv/bin/python attacks/bootstrap.py
echo
echo 'Setup complete. Start all five services: bash start_service.sh'
echo 'Credentials: instance/setup-credentials.json (keep private).'
echo 'Bank: http://bank.localhost:5000 | Playground: http://evil.bank.localhost:5001/playground'
echo 'On a VM, use SSH forwarding for local admin access, then configure public URLs in admin UI.'
