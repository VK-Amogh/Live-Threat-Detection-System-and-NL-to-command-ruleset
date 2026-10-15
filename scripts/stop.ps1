$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$record = Join-Path $projectRoot 'storage/server-processes.json'
if (!(Test-Path -LiteralPath $record)) { Write-Output 'No recorded server processes.'; return }
$items = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach ($item in $items) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($item.pid)" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine.Contains('uvicorn') -and $process.CommandLine.Contains("$($item.port)") -and $process.ExecutablePath.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $item.pid
        Write-Output "Stopped $($item.name)."
    }
}
