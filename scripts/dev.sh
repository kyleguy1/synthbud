#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  echo "Backend virtualenv not found at backend/.venv."
  echo "Create it with: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required but not installed."
  exit 1
fi

ensure_postgres() {
  local compose_file="$ROOT_DIR/backend/docker-compose.yml"

  if [[ ! -f "$compose_file" ]]; then
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed; assuming Postgres is managed outside Docker."
    return 0
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but not running; assuming Postgres is managed outside Docker."
    return 0
  fi

  echo "Ensuring Postgres is running (docker compose)..."
  docker compose -f "$compose_file" up -d postgres >/dev/null
}

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

ensure_postgres

(
  cd "$ROOT_DIR/backend"
  exec ./.venv/bin/python -m app
) &
BACKEND_PID=$!

echo "Starting backend on http://localhost:8000 ..."
for _ in $(seq 1 30); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
    echo "Backend exited during startup."
    exit 1
  fi

  if command -v curl >/dev/null 2>&1; then
    if curl -fsS http://localhost:8000/api/health/ >/dev/null 2>&1; then
      break
    fi
  fi

  sleep 1
done

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS http://localhost:8000/api/health/ >/dev/null 2>&1; then
    echo "Backend started, but DB health check failed at http://localhost:8000/api/health/."
    echo "Start Postgres (for Docker: cd backend && docker compose up -d) and retry."
    exit 1
  fi
fi

(
  cd "$ROOT_DIR/frontend"
  exec npm run dev
) &
FRONTEND_PID=$!

echo "Started backend (PID $BACKEND_PID) and frontend (PID $FRONTEND_PID)."
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000/api/docs"
echo "Press Ctrl+C to stop both."

# Portable "wait for first process to exit" (works on macOS bash 3.x).
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  wait "$BACKEND_PID"
  STATUS=$?
else
  wait "$FRONTEND_PID"
  STATUS=$?
fi

if kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; then
  echo "A service exited unexpectedly. Stopping both..."
fi

exit "$STATUS"
