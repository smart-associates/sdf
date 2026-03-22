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

# Dev mode
echo "Starting in dev mode..."

# Auto-detect database only if DATABASE_URL is not already set (via .env or environment)
if [ -z "$DATABASE_URL" ] && ! grep -q '^DATABASE_URL=' backend/.env 2>/dev/null; then
  if pg_isready -q 2>/dev/null; then
    echo "PostgreSQL detected — using PostgreSQL backend"
    if ! psql -h /var/run/postgresql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw sdf; then
      echo "Creating 'sdf' database..."
      createdb -h /var/run/postgresql sdf
    fi
    export DATABASE_URL="postgresql+asyncpg:///sdf?host=/var/run/postgresql"
    export SYNC_DATABASE_URL="postgresql+psycopg2:///sdf?host=/var/run/postgresql"
  else
    echo "PostgreSQL not running — falling back to SQLite"
    export DATABASE_URL="sqlite+aiosqlite:///./sdf.db"
    export SYNC_DATABASE_URL="sqlite:///./sdf.db"
  fi
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

# Wait for backend to be ready
echo "Waiting for backend to start..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://localhost:8000/docs 2>/dev/null; then
    echo "Backend is ready."
    break
  fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "ERROR: Backend process failed to start."
    exit 1
  fi
  sleep 1
done

if ! curl -s -o /dev/null http://localhost:8000/docs 2>/dev/null; then
  echo "ERROR: Backend did not become ready within 30 seconds."
  kill $BACKEND_PID 2>/dev/null
  exit 1
fi

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
