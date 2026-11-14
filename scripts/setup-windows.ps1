# JD Scorer - Windows prerequisites (run ONCE in an *Administrator* PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1
#
# Installs: WSL2 + Ubuntu 24.04, Docker Desktop, VS Code (+ WSL extension).
# Restart the PC afterwards, then follow the "After restart" steps printed at the end.

$ErrorActionPreference = 'Continue'

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Please run this from an Administrator PowerShell (right-click PowerShell > Run as administrator).' -ForegroundColor Red
    exit 1
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host 'winget not found. Install "App Installer" from the Microsoft Store, then re-run.' -ForegroundColor Red
    exit 1
}

Step 'WSL2 + Ubuntu 24.04'
# wsl.exe prints UTF-16; strip NUL chars before matching.
$distros = (wsl.exe -l -q 2>$null) -replace "`0", ''
if ($distros -match 'Ubuntu-24.04') {
    Write-Host 'Ubuntu-24.04 already installed.'
} else {
    wsl.exe --install -d Ubuntu-24.04 --no-launch
}
wsl.exe --set-default-version 2 2>$null | Out-Null

Step 'Docker Desktop'
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements

Step 'VS Code'
winget install -e --id Microsoft.VisualStudioCode --accept-package-agreements --accept-source-agreements

$code = Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\bin\code.cmd'
if (-not (Test-Path $code)) { $code = 'C:\Program Files\Microsoft VS Code\bin\code.cmd' }
if (Test-Path $code) {
    Step 'VS Code WSL extension'
    & $code --install-extension ms-vscode-remote.remote-wsl
}

Write-Host @'

============================================================
 Done. Now RESTART the PC. After restart:

 1. Open "Ubuntu 24.04" from the Start menu and create your
    Linux username + password.
 2. Open Docker Desktop, accept its terms, and in
    Settings > Resources > WSL integration enable "Ubuntu-24.04".
 3. In the Ubuntu window run:

    bash "/mnt/z/JD parsing/jd-scorer/scripts/setup-wsl.sh"

============================================================
'@ -ForegroundColor Green
