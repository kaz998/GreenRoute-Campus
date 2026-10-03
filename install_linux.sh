#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it with your Linux distribution's package manager."
  exit 1
fi

PYTHON_BIN="python3"
if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
  echo "Python venv support is missing. On Debian/Ubuntu, install the python3-venv package."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  "$PYTHON_BIN" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

if [ ! -f data/greenroute.db ]; then
  echo "First launch: loading demo data..."
  python seed.py
fi

echo
echo "Linux setup complete. Start the app with: ./run.sh"
