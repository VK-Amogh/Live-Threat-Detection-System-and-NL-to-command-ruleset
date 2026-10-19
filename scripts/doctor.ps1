# SafeSpace doctor: checks the server, the detector, Gemma, the firewall, the network and the APK, and says what to fix.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$hotspotSsid = 'Nothing Phone (4a)_7495'
function Row($label, $ok, $detail) { Write-Output ("{0,-22} {1,-5} {2}" -f $label, $(if ($ok) { 'PASS' } else { 'FAIL' }), $detail) }

Write-Output '=== SafeSpace doctor ==='
$wlan = netsh wlan show interfaces | Out-String
$ssid = if ($wlan -match '(?m)^\s*SSID\s*:\s*(.+)$') { $Matches[1].Trim() } else { '(not connected)' }
Row 'Laptop Wi-Fi' ($ssid -eq $hotspotSsid) "on '$ssid'$(if ($ssid -ne $hotspotSsid) { " (join '$hotspotSsid' with the hotspot on)" })"

$identity = $null
try { $identity = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health/identity' -TimeoutSec 3 } catch {}
Row 'API :8000' ([bool]$identity) $(if ($identity) { "server_id=$($identity.server_id)" } else { 'not running (scripts/start.ps1)' })
$https = [bool](Get-NetTCPConnection -State Listen -LocalPort 8443 -ErrorAction SilentlyContinue)
Row 'HTTPS :8443' $https $(if ($https) { 'listening (pinned TLS for the app)' } else { 'not listening' })

$token = ''
$envFile = Join-Path $root '.env'
if (Test-Path $envFile) { $m = Select-String -Path $envFile -Pattern '^INTERNAL_SERVICE_TOKEN=(.*)$' | Select-Object -First 1; if ($m) { $token = $m.Matches[0].Groups[1].Value.Trim() } }
$detector = $null
try { $detector = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 3 } catch {}
Row 'Detector :8001' ($detector -and $detector.ready) $(if ($detector -and $detector.ready) { 'YOLO + verifier + violence ready' } elseif ($detector) { 'loading models (about 30 s)' } else { 'not running' })

$tags = $null
try { $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 } catch {}
$gemma = $tags -and ($tags.models | Where-Object { $_.name -like 'gemma*' })
Row 'Gemma (Ollama)' ([bool]$gemma) $(if ($gemma) { ($gemma | Select-Object -First 1).name } elseif ($tags) { 'Ollama up, no gemma model (scripts/install-local-chat.py)' } else { 'Ollama not running' })

$needed = 'SafeSpace API http (8000)', 'SafeSpace API https (8443)', 'SafeSpace discovery (UDP 47800)'
$missing = $needed | Where-Object { !(Get-NetFirewallRule -DisplayName $_ -ErrorAction SilentlyContinue) }
Row 'Firewall rules' ($missing.Count -eq 0) $(if ($missing.Count -eq 0) { 'all three present' } else { 'missing: ' + ($missing -join '; ') + '  ->  scripts/network-setup.ps1 -Apply (as Administrator)' })

$hotspotIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -like '10.11.229.*' } | Select-Object -First 1
Row 'Hotspot address' ([bool]$hotspotIp) $(if ($hotspotIp) { "phones use http://$($hotspotIp.IPAddress):8000" } else { 'laptop has no 10.11.229.x address yet' })

$cameras = ''
try {
    $cfg = Get-Content -Raw (Join-Path $root 'config\network.yaml') | Select-String -Pattern '(?m)^mode:\s*(\S+)'
    $cameras = "network mode: $($cfg.Matches[0].Groups[1].Value)"
} catch {}
Row 'Network policy' $true $cameras

foreach ($kind in @(@('Release APK', 'SafeSpace.apk'), @('Debug APK', 'SafeSpace-debug.apk'))) {
    $apk = Join-Path $root ("storage\dist\" + $kind[1])
    if (Test-Path $apk) { Row $kind[0] $true ("{0} MB, built {1:g}" -f [math]::Round((Get-Item $apk).Length / 1MB, 1), (Get-Item $apk).LastWriteTime) }
    elseif ($kind[0] -eq 'Release APK') { Row $kind[0] $false 'missing (scripts/build-apk.ps1)' }
}
