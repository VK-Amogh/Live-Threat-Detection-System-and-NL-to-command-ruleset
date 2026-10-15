param([switch]$Build, [int]$Port = 8000)
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
$env:PYTHONPATH = "$projectRoot\contracts\src;$projectRoot\services\api;$projectRoot\services\inference"
$processes = @()
foreach ($service in @(@{Name='inference'; Port=8001; App='server:app'; Host='127.0.0.1'}, @{Name='api'; Port=$Port; App='app.main:app'; Host='0.0.0.0'})) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $service.Port -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $($service.Port) is already in use. Stop the previous server before launching." }
    $process = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn',$service.App,'--host',$service.Host,'--port',"$($service.Port)") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot\storage\logs\$($service.Name).log" -RedirectStandardError "$projectRoot\storage\logs\$($service.Name).error.log"
    $processes += @{name=$service.Name;pid=$process.Id;port=$service.Port}
}
$processes | ConvertTo-Json | Set-Content -LiteralPath storage/server-processes.json
$ollama = Join-Path $projectRoot 'storage\runtime\ollama\ollama.exe'
if ((Test-Path -LiteralPath $ollama) -and !(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue)) {
    $env:OLLAMA_HOST='127.0.0.1:11434'
    $env:OLLAMA_MODELS="$projectRoot\storage\ollama\models"
    $env:OLLAMA_NUM_PARALLEL='1'
    $env:OLLAMA_MAX_LOADED_MODELS='1'
    $env:OLLAMA_FLASH_ATTENTION='1'
    $env:OLLAMA_KV_CACHE_TYPE='q8_0'
    Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden -WorkingDirectory $projectRoot
}
Write-Output "Dashboard: http://localhost:$Port"
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.PrefixOrigin -ne 'WellKnown' } | ForEach-Object { Write-Output "Mobile server address: http://$($_.IPAddress):$Port" }
Write-Output 'Logs: storage/logs. Windows may require allowing this server on your private network.'
