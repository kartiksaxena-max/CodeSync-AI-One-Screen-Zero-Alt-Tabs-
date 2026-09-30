#!/usr/bin/env bash
# One command: ./run.sh   (creates .venv, installs, starts the app on http://localhost:8000)
# Needs Python 3.10, 3.11 or 3.12. Python 3.13+ is not supported by the OCR package yet.
set -e
cd "$(dirname "$0")"
PY=""
for c in python3.12 python3.11 python3.10; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10, 3.11 or 3.12 not found. On a Mac: brew install python@3.12  (or install it from python.org)"
  exit 1
fi
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "Open http://localhost:8000"
python -m uvicorn backend.app:app --port 8000
