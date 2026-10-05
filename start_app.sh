#!/usr/bin/env bash
# Starts the FastAPI backend (port 8000) and the Next.js website (port 3000).
# Usage:  bash start_app.sh      (then open http://localhost:3000, Ctrl+C to stop both)
cd "$(dirname "$0")"
source .venv/bin/activate
[ -d frontend/node_modules ] || (cd frontend && npm install)
python -m uvicorn backend.main:app --port 8000 &
API=$!
trap "kill $API 2>/dev/null" EXIT
cd frontend && npm run dev
