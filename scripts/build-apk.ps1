param([switch]$Debug)
# Builds the SafeSpace APK already configured for this laptop: its addresses, its TLS key pin, its shared secret.
#   scripts/build-apk.ps1            release APK  -> storage/dist/SafeSpace.apk
#   scripts/build-apk.ps1 -Debug     debug APK (installs beside the real app as com.safespace.safespace_mobile.dev)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Python environment missing. Run scripts/setup.ps1 first.' }

& $python scripts/apk_config.py
if ($LASTEXITCODE -ne 0) { throw 'Could not write the APK configuration.' }

Push-Location apps\mobile
try {
    $mode = if ($Debug) { '--debug' } else { '--release' }
    $ErrorActionPreference = 'Continue'   # flutter writes harmless warnings to stderr; judge success by exit code
    flutter build apk $mode --dart-define-from-file=.dart_defines.json
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) { throw 'flutter build failed.' }
} finally { Pop-Location }

$built = Join-Path $root ("apps\mobile\build\app\outputs\flutter-apk\" + $(if ($Debug) { 'app-debug.apk' } else { 'app-release.apk' }))
New-Item -ItemType Directory -Force storage\dist | Out-Null
$target = Join-Path $root ("storage\dist\" + $(if ($Debug) { 'SafeSpace-debug.apk' } else { 'SafeSpace.apk' }))
Copy-Item -LiteralPath $built -Destination $target -Force
Write-Output ("APK ready: $target  (" + [math]::Round((Get-Item $target).Length / 1MB, 1) + ' MB)')
Write-Output 'Install: scan the APK QR on the dashboard (System > APK download link), or: adb install -r <file>'
