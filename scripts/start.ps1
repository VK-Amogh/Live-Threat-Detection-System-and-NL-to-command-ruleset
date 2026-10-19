param([switch]$Build, [int]$Port = 8000)
# Starts the whole SafeSpace stack: threat detector (YOLO + verifier + violence), API + dashboard (HTTP and HTTPS),
# the rule manager, the visual reasoner, and Ollama (Gemma). Phones join over the Nothing Phone hotspot.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Python environment missing. Run scripts/setup.ps1 first.' }
if (!(Test-Path -LiteralPath '.env')) { throw 'Create .env from .env.example and set your credentials.' }
if ($Build -or !(Test-Path -LiteralPath 'apps/dashboard/dist/index.html')) {
    Push-Location apps/dashboard
    try { npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'Dashboard install failed' }; npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed' } } finally { Pop-Location }
}
New-Item -ItemType Directory -Force storage/logs | Out-Null
$env:PYTHONPATH = "$projectRoot;$projectRoot\contracts\src;$projectRoot\services\api;$projectRoot\services\inference"
$env:API_PORT = "$Port"
foreach ($p in @(8001, $Port)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) { throw "Port $p is already in use. Run scripts/stop.ps1 (or stop the old server) before launching." }
}
$processes = @()
function Launch($name, $arguments, $port) {
    $proc = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$projectRoot\storage\logs\$name.log" -RedirectStandardError "$projectRoot\storage\logs\$name.error.log"
    $script:processes += @{name=$name;pid=$proc.Id;port=$port}
}
# 1. Threat detector (loopback only). Models take ~30 s to load, the API does not wait for it.
Launch 'inference' @('-m','uvicorn','server:app','--app-dir','services/inference','--host','127.0.0.1','--port','8001') 8001
# 2. API + dashboard: HTTP :$Port and HTTPS :8443 from one process (services/api/serve.py).
Launch 'api' @('services/api/serve.py') $Port
$env:SAFESPACE_API_URL = "http://127.0.0.1:$Port"
Launch 'rule-manager' @('-m','services.rules.manager') 0
Launch 'reasoner' @('-m','services.reasoner.loop') 0
$processes | ConvertTo-Json | Set-Content -LiteralPath storage/server-processes.json
# 3. Gemma through Ollama (everything on the GPU; see .env OLLAMA_NUM_GPU).
$ollama = Join-Path $projectRoot 'storage\runtime\ollama\ollama.exe'
if ((Test-Path -LiteralPath $ollama) -and !(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue)) {
    $env:OLLAMA_HOST='127.0.0.1:11434'
    $env:OLLAMA_MODELS="$projectRoot\storage\ollama\models"
    $env:OLLAMA_NUM_PARALLEL='1'
    $env:OLLAMA_MAX_LOADED_MODELS='1'
    $env:OLLAMA_FLASH_ATTENTION='1'
    $env:OLLAMA_KV_CACHE_TYPE='q8_0'
    Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden -WorkingDirectory $projectRoot | Out-Null
}
# 4. Wait until it is really up, and say what is not.
Write-Output 'Starting SafeSpace…'
$deadline = (Get-Date).AddSeconds(120)
$state = @{api=$false; detector=$false; ollama=$false}
while ((Get-Date) -lt $deadline -and ($state.Values -contains $false)) {
    Start-Sleep -Seconds 2
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$Port/api/v1/health/live").StatusCode -eq 200) { $state.api = $true } } catch {}
    try { if ((Invoke-RestMethod -TimeoutSec 2 "http://127.0.0.1:11434/api/tags")) { $state.ollama = $true } } catch {}
    try { $h = Invoke-RestMethod -TimeoutSec 2 -Headers @{Authorization = "Bearer $((Get-Content .env | Select-String '^INTERNAL_SERVICE_TOKEN=').ToString().Split('=',2)[1])"} http://127.0.0.1:8001/health; if ($h.ready) { $state.detector = $true } } catch {}
}
Write-Output ("API + dashboard : " + $(if ($state.api) { "ready  http://localhost:$Port" } else { 'NOT READY (see storage/logs/api.error.log)' }))
Write-Output ("Threat detector : " + $(if ($state.detector) { 'ready (YOLO + verifier + violence)' } else { 'NOT READY (see storage/logs/inference.error.log)' }))
Write-Output ("Gemma (Ollama)  : " + $(if ($state.ollama) { 'ready' } else { 'NOT READY (see storage/logs; run scripts/install-local-chat.py once)' }))
$hotspot = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -like '10.11.229.*' }
if ($hotspot) { Write-Output "Phones (Nothing Phone hotspot): http://$($hotspot.IPAddress):$Port" }
else {
    $ssid = (netsh wlan show interfaces | Select-String -Pattern '^\s*SSID\s*:\s*(.+)$' | Select-Object -First 1).Matches.Groups[1].Value
    Write-Output "This laptop is on '$ssid', not the Nothing Phone hotspot. Join 'Nothing Phone (4a)_7495' so phones can reach it (USB works now: adb reverse tcp:$Port tcp:$Port)."
}
Write-Output 'Logs: storage/logs'
