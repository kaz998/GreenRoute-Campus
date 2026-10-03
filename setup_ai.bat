@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Run run.bat once first.
  pause
  exit /b 1
)
call .venv\Scripts\activate
python setup_ai.py
pause
