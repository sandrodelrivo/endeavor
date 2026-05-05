@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Installing dependencies...
    .venv\Scripts\pip install -e . --quiet
)

echo.
echo Starting Structure Manager at http://localhost:8765
echo Press Ctrl+C to stop.
echo.

.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8765 --reload

endlocal
