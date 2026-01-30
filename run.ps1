$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# Always run from this script's directory
Set-Location -Path $PSScriptRoot

# 1) Ensure venv exists
if (!(Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Creating venv..."
  python -m venv .venv
}

# 2) Use venv python
$py = ".\.venv\Scripts\python.exe"

Write-Host "Using Python: $py"
& $py --version

# 3) Install deps (idempotent)
Write-Host "Installing dependencies..."
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

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
