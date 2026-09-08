@echo off
setlocal

cd /d "%~dp0"
set "ROOT=%~dp0"

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo [ERROR] Backend Python environment not found: %ROOT%.venv\Scripts\python.exe
  pause
  exit /b 1
)

if not exist "%ROOT%algorithm\.venv\Scripts\python.exe" (
  echo [ERROR] Algorithm Python environment not found: %ROOT%algorithm\.venv\Scripts\python.exe
  pause
  exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
  echo [ERROR] Frontend dependencies not found. Run npm install in frontend first.
  pause
  exit /b 1
)

echo Starting AI Teaching Evaluation System...

start "AI Teaching Backend" /min cmd /k "cd /d "%ROOT%backend" && "%ROOT%.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
start "AI Teaching Algorithm" /min cmd /k "cd /d "%ROOT%algorithm" && "%ROOT%algorithm\.venv\Scripts\python.exe" -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload"
start "AI Teaching Frontend" /min cmd /k "cd /d "%ROOT%frontend" && npm.cmd run dev -- --host 0.0.0.0"

echo Services:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000/docs
echo   AI:       http://localhost:8001/docs
echo.
echo Opening frontend page...
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"

exit /b 0
