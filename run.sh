#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.11+ and try again."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add your own API key if cloud AI is required."
fi

if [ ! -f data/greenroute.db ]; then
  echo "First launch: loading demo data..."
  python seed.py
else
  echo "Existing database found. Keeping your saved trips and account data."
fi

echo
echo "GreenRoute Campus is starting at http://localhost:5000"
python -m flask --app 'app:create_app()' run --host 0.0.0.0 --port 5000
