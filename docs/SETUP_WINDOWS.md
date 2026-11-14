# One-time setup on Windows (WSL2 + Docker Desktop)

Takes about 20–30 minutes, mostly downloads. You only do this once per machine.

## Fast path (scripted)

1. Copy `scripts\setup-windows.ps1` to your Desktop (an Administrator window may not see the `Z:` drive).
2. Open **PowerShell as Administrator** and run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Desktop\setup-windows.ps1"
   ```
3. **Restart** the PC. Open **Ubuntu 24.04** from Start and create your Linux user. Open **Docker Desktop**, accept its terms, enable *Settings → Resources → WSL integration → Ubuntu-24.04*.
4. In the Ubuntu window:
   ```bash
   bash "/mnt/z/JD parsing/jd-scorer/scripts/setup-wsl.sh"
   ```

That's it. The manual steps below are what the scripts do, in case something needs fixing by hand.

## 1. Install WSL2 with Ubuntu

1. Open **PowerShell as Administrator** (Start → type "PowerShell" → right-click → *Run as administrator*).
2. Run:
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```
3. **Restart** the PC when asked.
4. Open **Ubuntu** from the Start menu. Create a Linux username and password (this is separate from your Windows login).
5. Check it's WSL **2**: in PowerShell run `wsl -l -v` → the VERSION column should say `2`.

## 2. Install Docker Desktop

1. Download and install Docker Desktop for Windows from docker.com.
2. Open Docker Desktop → **Settings**:
   - *General* → ✅ **Use the WSL 2 based engine**
   - *Resources → WSL integration* → ✅ enable for **Ubuntu-24.04**
3. Apply & restart Docker Desktop.
4. In the Ubuntu terminal: `docker run --rm hello-world` → should print "Hello from Docker!".

## 3. Install VS Code + WSL extension

1. Install VS Code (Windows).
2. Install the extension **"WSL"** (by Microsoft).
3. From now on, open the project from Ubuntu with `code .` — VS Code shows **"WSL: Ubuntu"** in the bottom-left corner.

## 4. Install developer tools inside Ubuntu

Run these in the **Ubuntu** terminal:

```bash
# basics
sudo apt update && sudo apt install -y git make curl build-essential

# uv (Python package/project manager; installs Python 3.12 for us)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv python install 3.12

# Node.js 22 LTS via nvm, then pnpm via corepack
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 22
corepack enable
corepack prepare pnpm@9.15.0 --activate

# git identity (use your own)
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git config --global core.autocrlf input
```

Check: `uv --version && node --version && pnpm --version && docker --version`

## 5. Get the project into WSL

The scaffold was created in `Z:\JD parsing\jd-scorer`. Work from a copy **inside** the Linux filesystem (much faster for Docker, file watching and git):

```bash
mkdir -p ~/code
cp -r "/mnt/z/JD parsing/jd-scorer" ~/code/jd-scorer
cd ~/code/jd-scorer
```

> If `/mnt/z` doesn't exist (Z: is a network/mapped drive), mount it once:
> `sudo mkdir -p /mnt/z && sudo mount -t drvfs Z: /mnt/z`
> or copy the folder to `C:\temp` in Explorer and use `/mnt/c/temp/jd-scorer`.

Once the repo is on GitHub, just `git clone` into `~/code` instead.

## 6. Run it

```bash
cd ~/code/jd-scorer
make setup      # install deps
make format     # one-time: let Prettier/ruff normalise formatting
make up         # Postgres (MinIO is opt-in for now)
make migrate
make check      # lint + typecheck + tests should be green
make dev-api    # terminal 1
make dev-web    # terminal 2 → open http://localhost:5173
```

Windows browsers reach WSL servers via `localhost` automatically.

Then make the first commit (lockfiles included):

```bash
git init -b main
git add -A
git commit -m "chore: initial project scaffold (phase 0)"
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` in Ubuntu | Docker Desktop → Settings → Resources → WSL integration → enable Ubuntu, restart terminal |
| `port 5432 already in use` | Another Postgres is running on Windows. Stop it, or set `POSTGRES_PORT=5433` in `.env` and update `DATABASE_URL` |
| Very slow `pnpm install` / hot reload | Repo is on `/mnt/c` or `/mnt/z`. Move it to `~/code` |
| `make: command not found` | `sudo apt install -y make` |
| Files show as changed with no edits | Line endings. `git config --global core.autocrlf input`, then `git add --renormalize .` |
| API badge says "unreachable" | Is `make dev-api` running? Check `curl localhost:8000/api/v1/healthz` |
