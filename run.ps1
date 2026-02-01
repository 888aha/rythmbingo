param(
  [switch]$ForceDeps
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"


chcp 65001 | Out-Null
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# Always run from this script's directory
Set-Location -Path $PSScriptRoot

# 1) Ensure venv exists
$venvCreated = $false
if (!(Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Creating venv..."
  python -m venv .venv
  $venvCreated = $true
}

# 2) Use venv python
$py = ".\.venv\Scripts\python.exe"

Write-Host "Using Python: $py"
& $py --version

# 3) Install deps (FAST after first run)
# Only (a) upgrade pip on fresh venv, and (b) install requirements if requirements.txt changed.
$req = Join-Path $PSScriptRoot "requirements.txt"
$stamp = Join-Path $PSScriptRoot ".\.venv\.deps_stamp"

if ($venvCreated) {
  Write-Host "Upgrading pip (fresh venv)..."
  & $py -m pip install --upgrade pip --disable-pip-version-check | Out-Null
}

$needInstall = $ForceDeps -or !(Test-Path $stamp)
if (-not $needInstall) {
  $needInstall = (Get-Item $req).LastWriteTimeUtc -gt (Get-Item $stamp).LastWriteTimeUtc
}

if ($needInstall) {
  Write-Host "Installing dependencies (requirements changed or first run)..."
  & $py -m pip install -r $req --disable-pip-version-check
  # Touch stamp so future runs skip this step unless requirements.txt changes
  Set-Content -Path $stamp -Value (Get-Date -Format o) -Encoding utf8
} else {
  Write-Host "Dependencies already installed (stamp is up to date). Skipping pip install."
}


# 4) Run pipeline
Write-Host "Running pipeline..."
& $py .\main.py

Write-Host ""
Write-Host "Done. Outputs:"
Write-Host " - tiles_svg\"
Write-Host " - rhythm_catalog.pdf"
Write-Host " - bingo_cards.pdf"
Write-Host " - out\pools.json"
Write-Host " - out\caller_cards.pdf"
Write-Host " - out\call_sheet.txt"
Write-Host " - out\deck_qc.csv"
