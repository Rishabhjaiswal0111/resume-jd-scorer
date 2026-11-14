#!/usr/bin/env bash
# JD Scorer - everything inside Ubuntu (WSL). Safe to re-run.
#
#   bash "/mnt/z/JD parsing/jd-scorer/scripts/setup-wsl.sh" [source-dir]
#
# Installs uv + Python 3.12, Node 22 + pnpm, copies the repo to ~/code/jd-scorer,
# installs dependencies, starts Postgres, runs migrations and the full check suite.

set -eo pipefail

SRC="${1:-/mnt/z/JD parsing/jd-scorer}"
DEST="$HOME/code/jd-scorer"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*"; exit 1; }

step "System packages (sudo will ask for your Ubuntu password)"
sudo apt-get update -y
sudo apt-get install -y git make curl ca-certificates build-essential

step "uv + Python 3.12"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.12

step "Node.js 22 + pnpm"
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm install 22
nvm alias default 22
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
corepack enable
corepack prepare pnpm@9.15.0 --activate

step "Docker"
if ! docker info >/dev/null 2>&1; then
  fail "Docker is not reachable from Ubuntu.
  Open Docker Desktop > Settings > Resources > WSL integration > enable 'Ubuntu-24.04' > Apply & restart,
  then re-run this script."
fi
echo "Docker OK: $(docker --version)"

step "Copy project into the Linux filesystem ($DEST)"
if [ -d "$DEST" ]; then
  echo "$DEST already exists - keeping it (delete it to re-copy)."
else
  if [ ! -d "$SRC" ] && [[ "$SRC" == /mnt/z/* ]]; then
    echo "Z: is not mounted in WSL yet - mounting it (network/mapped drive)."
    sudo mkdir -p /mnt/z
    sudo mount -t drvfs Z: /mnt/z || true
  fi
  [ -d "$SRC" ] || fail "Can't find the project at '$SRC'.
  Copy the jd-scorer folder to C:\\temp in Explorer and run:
  bash /mnt/c/temp/jd-scorer/scripts/setup-wsl.sh /mnt/c/temp/jd-scorer"
  mkdir -p "$HOME/code"
  cp -r "$SRC" "$DEST"
  # Files copied from Windows can arrive with odd permissions / CRLF; normalise scripts.
  find "$DEST" -name '*.sh' -exec sed -i 's/\r$//' {} + -exec chmod +x {} +
fi
cd "$DEST"

step "git"
git config --global core.autocrlf input
[ -d .git ] || git init -b main

step "Install dependencies"
make setup

step "Normalise formatting (one-time)"
make format

step "Start Postgres"
make up

step "Database migrations"
make migrate

step "Lint + typecheck + tests"
if make check; then
  CHECK="all green"
else
  CHECK="some checks FAILED - copy the output above and paste it to Claude"
fi

cat <<EOF

============================================================
 Setup finished: $CHECK

 Project: $DEST
 Open it in VS Code:   cd $DEST && code .

 Run the app (two terminals):
   make dev-api    -> http://localhost:8000/docs
   make dev-web    -> http://localhost:5173

 First commit (set your git name/email first):
   git config --global user.name  "Your Name"
   git config --global user.email "you@example.com"
   git add -A && git commit -m "chore: initial project scaffold (phase 0)"
============================================================
EOF
