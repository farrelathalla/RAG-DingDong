@echo off
cd /d "%~dp0"

if not exist .env (
  echo Copying .env.example to .env...
  copy .env.example .env
  echo.
  echo Please edit .env and add your GEMINI_API_KEY, then re-run this script.
  echo Get your free Gemini API key at: https://aistudio.google.com/apikey
  pause
  exit /b 1
)

echo Installing dependencies...
pip install -r backend/requirements.txt

echo.
echo Starting RAG-DingDong server at http://localhost:8000
echo Press Ctrl+C to stop.
echo.
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
