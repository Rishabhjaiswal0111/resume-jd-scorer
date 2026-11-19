#!/usr/bin/env bash
# One command to run the app: Docker -> Postgres -> migrations -> API + web -> wait until
# both answer -> open the browser. Safe to re-run: anything already running is reused.
#   make start   |   make stop   |   make pending
set -euo pipefail
cd "$(dirname "$0")/.."

API=http://localhost:8000
WEB=http://localhost:5173
RUN=var/run
LOGS=var/logs
MANUAL=backend/var/manual_llm
mkdir -p "$RUN" "$LOGS"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*"; }

api_ready() { curl -sf "$API/api/v1/readyz" >/dev/null 2>&1; }
web_ready() { curl -sf -o /dev/null "$WEB" 2>/dev/null; }

wait_for() { # name, check function, seconds, log file
  local name=$1 check=$2 secs=$3 log=$4
  for _ in $(seq 1 "$secs"); do
    if $check; then green "  ✓ $name is ready"; return 0; fi
    sleep 1
  done
  red "  ✗ $name did not become ready in ${secs}s. Last log lines ($log):"
  tail -n 20 "$log" 2>/dev/null || true
  exit 1
}

start_bg() { # name, log, command...  (own process group, so `make stop` kills reloaders too)
  local name=$1 log=$2; shift 2
  setsid nohup "$@" >"$log" 2>&1 &
  echo $! >"$RUN/$name.pid"
}

echo "1/4 Docker"
if ! docker info >/dev/null 2>&1; then
  DESKTOP="/mnt/c/Program Files/Docker/Docker/Docker Desktop.exe"
  if [ -x "$DESKTOP" ]; then
    yellow "  Docker is not running; starting Docker Desktop..."
    (cd /mnt/c && "$DESKTOP" >/dev/null 2>&1 &)
  fi
  for _ in $(seq 1 120); do docker info >/dev/null 2>&1 && break; sleep 1; done
  docker info >/dev/null 2>&1 || { red "  ✗ Docker did not start. Open Docker Desktop and re-run."; exit 1; }
fi
green "  ✓ Docker is running"

echo "2/4 Postgres + migrations"
docker compose --env-file .env up -d --wait postgres >/dev/null 2>&1 \
  || { red "  ✗ Postgres failed to start (try: docker compose logs postgres)"; exit 1; }
uv --directory backend run alembic upgrade head >"$LOGS/migrate.log" 2>&1 \
  || { red "  ✗ Migration failed:"; tail -n 20 "$LOGS/migrate.log"; exit 1; }
green "  ✓ Postgres healthy, database up to date"

echo "3/4 API and web"
if api_ready; then
  green "  ✓ API already running"
else
  start_bg api "$LOGS/api.log" uv --directory backend run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  wait_for "API ($API)" api_ready 60 "$LOGS/api.log"
fi
if web_ready; then
  green "  ✓ Web already running"
else
  start_bg web "$LOGS/web.log" pnpm --dir frontend dev
  wait_for "Web ($WEB)" web_ready 60 "$LOGS/web.log"
fi

echo "4/4 Open"
MODEL=$(grep -E '^LLM_DEFAULT_MODEL=' .env | cut -d= -f2 | awk '{print $1}')
echo "  Model: ${MODEL:-anthropic/claude-haiku-5-5 (default)}"
PENDING=$(scripts/pending.sh --count)
if [ "$PENDING" -gt 0 ]; then
  yellow "  $PENDING manual prompt(s) waiting for an answer (make pending)"
fi
if command -v cmd.exe >/dev/null 2>&1; then
  (cd /mnt/c && cmd.exe /c start "" "$WEB" >/dev/null 2>&1) || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$WEB" >/dev/null 2>&1 || true
fi
green "Ready: $WEB   (API docs: $API/docs · logs: $LOGS/ · stop: make stop)"
