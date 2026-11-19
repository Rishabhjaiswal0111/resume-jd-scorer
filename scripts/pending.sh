#!/usr/bin/env bash
# Manual LLM mode: list prompts in backend/var/manual_llm that have no answer file yet.
#   scripts/pending.sh          -> one line per pending prompt (newest first)
#   scripts/pending.sh --count  -> just the number
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=backend/var/manual_llm
count=0
lines=()
if [ -d "$DIR" ]; then
  while IFS= read -r req; do
    [ -n "$req" ] || continue
    [ -f "${req%.request.md}.response.json" ] && continue
    count=$((count + 1))
    purpose=$(head -1 "$req" | sed 's/^# //')
    lines+=("$(date -r "$req" '+%Y-%m-%d %H:%M')  $purpose  $req")
  done < <(ls -t "$DIR"/*.request.md 2>/dev/null || true)
fi
if [ "${1:-}" = "--count" ]; then
  echo "$count"
  exit 0
fi
if [ "$count" -eq 0 ]; then
  echo "No manual prompts waiting."
else
  echo "$count manual prompt(s) waiting for an answer:"
  printf '  %s\n' "${lines[@]}"
  echo "Write <hash>.response.json next to each one (or ask Claude Code); the open page continues on its own."
fi
