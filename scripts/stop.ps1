$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$record = Join-Path $projectRoot 'storage/server-processes.json'
if (!(Test-Path -LiteralPath $record)) { Write-Output 'No recorded server processes.'; return }
$items = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
$workersRecord = Join-Path $projectRoot 'storage/worker-processes.json'
if (Test-Path -LiteralPath $workersRecord) {
    $workers = Get-Content -LiteralPath $workersRecord -Raw | ConvertFrom-Json
    foreach ($property in $workers.PSObject.Properties) {
        $workerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($property.Value)" -ErrorAction SilentlyContinue
        if ($workerProcess -and $workerProcess.CommandLine.Contains('services.rules.worker') -and $workerProcess.ExecutablePath.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $property.Value
            Write-Output "Stopped rule worker $($property.Name)."
        }
    }
}
foreach ($item in $items) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($item.pid)" -ErrorAction SilentlyContinue
    if (!$process) { continue }
    $matchesService = ($item.name -eq 'rule-manager' -and $process.CommandLine.Contains('services.rules.manager')) -or ($item.name -eq 'reasoner' -and $process.CommandLine.Contains('services.reasoner.loop'))
    $matchesUvicorn = $item.name -in @('api','inference') -and $process.CommandLine.Contains('uvicorn') -and $process.CommandLine.Contains("$($item.port)")
    if (($matchesService -or $matchesUvicorn) -and $process.ExecutablePath.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $item.pid
        Write-Output "Stopped $($item.name)."
    }
}
