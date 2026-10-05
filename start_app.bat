@echo off
REM Starts the FastAPI backend (port 8000) in a new window and the Next.js website (port 3000).
REM Usage: double-click this file, or run  start_app.bat  from the RetinaAI folder.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run:  py -m venv .venv  and  pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  popd
)
start "RetinaAI backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --port 8000"
cd frontend
call npm run dev
