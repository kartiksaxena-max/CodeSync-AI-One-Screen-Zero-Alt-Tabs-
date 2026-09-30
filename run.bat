@echo off
rem One command on Windows: run.bat   (needs Python 3.10 to 3.12)
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo Open http://localhost:8000
start "" http://localhost:8000
python -m uvicorn backend.app:app --port 8000
