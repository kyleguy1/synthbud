#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="http://localhost:8000"
BACKEND_HEALTH_URL="$BACKEND_URL/api/health/"
MANAGED_BACKEND=0

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

backend_health_ok() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi

  curl -fsS "$BACKEND_HEALTH_URL" >/dev/null 2>&1
}

find_backend_listener_pid() {
  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi

  lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null | head -n 1
}

wait_for_backend_port_to_clear() {
  for _ in $(seq 1 20); do
    if [[ -z "$(find_backend_listener_pid || true)" ]]; then
      return 0
    fi
    sleep 0.25
  done

  return 1
}

ensure_backend_port_ready() {
  local existing_pid
  existing_pid="$(find_backend_listener_pid || true)"

  if [[ -z "$existing_pid" ]]; then
    return 0
  fi

  if backend_health_ok; then
    echo "Backend already running at $BACKEND_URL; reusing existing process (PID $existing_pid)."
    return 0
  fi

  local existing_cmd
  existing_cmd="$(ps -p "$existing_pid" -o command= 2>/dev/null || true)"

  if [[ "$existing_cmd" == *"$ROOT_DIR/backend"* && "$existing_cmd" == *"-m app"* ]]; then
    echo "Stopping stale backend process on port 8000 (PID $existing_pid)."
    kill "$existing_pid" 2>/dev/null || true

    if ! wait_for_backend_port_to_clear; then
      echo "Port 8000 is still busy after stopping the stale backend process."
      echo "Please free the port manually, then retry."
      exit 1
    fi

    return 0
  fi

  echo "Port 8000 is already in use by a different process:"
  echo "  PID $existing_pid: ${existing_cmd:-unknown command}"
  echo "Stop that process or change the port before running ./scripts/dev.sh."
  exit 1
}

cleanup() {
  if [[ "$MANAGED_BACKEND" -eq 1 ]] && [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

ensure_postgres
ensure_backend_port_ready

if backend_health_ok; then
  echo "Using existing healthy backend at $BACKEND_URL."
else
  (
    cd "$ROOT_DIR/backend"
    exec ./.venv/bin/python -m app
  ) &
  BACKEND_PID=$!
  MANAGED_BACKEND=1

  echo "Starting backend on $BACKEND_URL ..."
  for _ in $(seq 1 30); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      wait "$BACKEND_PID"
      echo "Backend exited during startup."
      exit 1
    fi

    if backend_health_ok; then
      break
    fi

    sleep 1
  done

  if command -v curl >/dev/null 2>&1; then
    if ! backend_health_ok; then
      echo "Backend started, but DB health check failed at $BACKEND_HEALTH_URL."
      echo "Start Postgres (for Docker: cd backend && docker compose up -d) and retry."
      exit 1
    fi
  fi
fi

(
  cd "$ROOT_DIR/frontend"
  exec npm run dev
) &
FRONTEND_PID=$!

if [[ "$MANAGED_BACKEND" -eq 1 ]]; then
  echo "Started backend (PID $BACKEND_PID) and frontend (PID $FRONTEND_PID)."
else
  echo "Started frontend (PID $FRONTEND_PID) and reused the existing backend."
fi
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000/api/docs"
echo "Press Ctrl+C to stop both."

# Portable "wait for first process to exit" (works on macOS bash 3.x).
if [[ "$MANAGED_BACKEND" -eq 1 ]]; then
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
else
  wait "$FRONTEND_PID"
  STATUS=$?
fi

if [[ "$MANAGED_BACKEND" -eq 1 ]] && kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; then
  echo "A service exited unexpectedly. Stopping both..."
fi

exit "$STATUS"
