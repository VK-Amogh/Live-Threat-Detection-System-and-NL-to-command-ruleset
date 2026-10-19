param([switch]$Apply, [switch]$IncludeIbus)
# Opens the Windows Firewall for the SafeSpace server so phones on the Nothing Phone hotspot can reach this laptop.
#   scripts/network-setup.ps1                 show what would change (changes nothing)
#   scripts/network-setup.ps1 -Apply          create the rules (run PowerShell as Administrator)
#   scripts/network-setup.ps1 -Apply -IncludeIbus   also allow the iBus subnet (HTTPS only is enforced by the server)
# It never changes your Wi-Fi connections or network profiles; join the hotspot yourself.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$hotspotSsid = 'Nothing Phone (4a)_7495'
$subnets = @('10.11.229.0/24')
if ($IncludeIbus) { $subnets += '10.12.0.0/16' }
$rules = @(
    @{ Name = 'SafeSpace API http (8000)';      Protocol = 'TCP'; Port = 8000 },
    @{ Name = 'SafeSpace API https (8443)';     Protocol = 'TCP'; Port = 8443 },
    @{ Name = 'SafeSpace discovery (UDP 47800)'; Protocol = 'UDP'; Port = 47800 }
)

Write-Output '=== SafeSpace network setup ==='
$wlan = netsh wlan show interfaces | Out-String
$ssid = if ($wlan -match '(?m)^\s*SSID\s*:\s*(.+)$') { $Matches[1].Trim() } else { '(not connected)' }
Write-Output "Laptop Wi-Fi : $ssid"
if ($ssid -ne $hotspotSsid) {
    Write-Output "NOTE: join '$hotspotSsid' (hotspot on) so phones can reach this laptop. Windows may auto-reconnect to iBus; turn off auto-connect for iBus if it keeps winning."
}
$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { $_.IPAddress }
Write-Output ("Laptop IPv4  : " + ($ips -join ', '))
Write-Output ("Allowed from : " + ($subnets -join ', '))

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
foreach ($r in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
    if ($existing) { Write-Output ("[present] {0}" -f $r.Name); continue }
    if (!$Apply) { Write-Output ("[would add] {0}  {1}/{2} from {3}" -f $r.Name, $r.Protocol, $r.Port, ($subnets -join ',')); continue }
    if (!$isAdmin) { Write-Output ("[needs Administrator] {0}" -f $r.Name); continue }
    New-NetFirewallRule -DisplayName $r.Name -Direction Inbound -Protocol $r.Protocol -LocalPort $r.Port -RemoteAddress $subnets -Profile Any -Action Allow | Out-Null
    Write-Output ("[added] {0}" -f $r.Name)
}
if (!$Apply) { Write-Output 'Dry run only. Re-run with -Apply from an Administrator PowerShell to create the missing rules.' }
elseif (!$isAdmin) { Write-Output 'Not elevated: open PowerShell as Administrator and run this again with -Apply.' }
