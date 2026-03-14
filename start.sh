#!/bin/bash
set -e

# Start SDF - Data Migration Tool
# Usage: ./start.sh [dev|docker]

MODE=${1:-dev}

if [ "$MODE" = "docker" ]; then
  echo "Starting with Docker Compose..."
  docker compose up --build
  exit 0
fi

# Dev mode: assumes PostgreSQL is running locally
echo "Starting in dev mode..."

# Copy .env if not present
if [ ! -f backend/.env ]; then
  cp .env.example backend/.env
  echo "Created backend/.env from .env.example — update values as needed"
fi

# Start backend
echo "Starting FastAPI backend on :8000..."
cd backend
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting Vite frontend on :5173..."
cd ui
npm install -q
npm run dev -- --host &
FRONTEND_PID=$!
cd ..

echo ""
echo "SDF is running:"
echo "  API:     http://localhost:8000"
echo "  Docs:    http://localhost:8000/docs"
echo "  UI:      http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
