$ErrorActionPreference = "Stop"

chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8


# Always run from this script's directory
Set-Location -Path $PSScriptRoot

# 1) Ensure venv exists
if (!(Test-Path ".\.venv\Scripts\python.exe")) {
  python -m venv .venv
}

# 2) Use venv python
$py = ".\.venv\Scripts\python.exe"

# 3) Upgrade pip and install deps (idempotent)
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt | Out-Null

# 4) Run pipeline
& $py .\render_tiles.py
& $py .\catalog_rhythms.py
& $py .\compose_cards.py

Write-Host "Done. Outputs:"
Write-Host " - tiles_svg\"
Write-Host " - rhythm_catalog.pdf"
Write-Host " - bingo_cards.pdf"
