#!/usr/bin/env bash
# Manual LLM mode helper: block until at least one prompt is waiting, then list it and exit.
# Used by a Claude Code session to get notified (run in the background) and answer it.
set -euo pipefail
cd "$(dirname "$0")/.."
while [ "$(scripts/pending.sh --count)" -eq 0 ]; do sleep 2; done
scripts/pending.sh
