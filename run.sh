#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Edit .env with your GEMINI_API_KEY, then re-run."
  echo "Get your free key at: https://aistudio.google.com/apikey"
  exit 1
fi

echo "Installing dependencies..."
pip install -r backend/requirements.txt

echo "Starting RAG-DingDong at http://localhost:8000"
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
