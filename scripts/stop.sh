#!/usr/bin/env bash
# Stop what `make start` started (API, web), then Postgres. Data is kept.
set -uo pipefail
cd "$(dirname "$0")/.."
for name in api web; do
  pidfile="var/run/$name.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    kill -- "-$pid" 2>/dev/null && echo "stopped $name" || echo "$name was not running"
    rm -f "$pidfile"
  fi
done
docker compose stop postgres >/dev/null 2>&1 && echo "stopped postgres"
