$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (!(Test-Path -LiteralPath '.env')) { Copy-Item .env.example .env }
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
uv pip install --python .venv/Scripts/python.exe torch torchvision --index-url https://download.pytorch.org/whl/cu128 --reinstall-package torch --reinstall-package torchvision
uv pip install --python .venv/Scripts/python.exe -e ./contracts
Push-Location apps/dashboard
try { npm.cmd ci; npm.cmd run build } finally { Pop-Location }
Write-Output 'Set credentials in .env, then run scripts/start.ps1. For local Gemma: .venv/Scripts/python scripts/install-local-chat.py'
