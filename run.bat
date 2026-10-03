@echo off
cd /d %~dp0
if not exist .venv\Scripts\python.exe py -3.11 -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if not exist .env copy /Y .env.example .env >nul
if not exist data\greenroute.db (
  echo First launch: loading demo data...
  python seed.py
) else (
  echo Existing database found. Keeping your saved trips and account data.
)
echo.
echo GreenRoute Campus is starting at http://localhost:5000
python -m flask --app "app:create_app()" run --host 0.0.0.0 --port 5000
