# SafeSpace Windows Firewall Configuration
# Allows inbound LAN traffic on port 8000 (Private network profile only)

New-NetFirewallRule -DisplayName "SafeSpace Threat Detection API (LAN :8000)" `
    -Direction Inbound `
    -LocalPort 8000 `
    -Protocol TCP `
    -Action Allow `
    -Profile Private `
    -Description "Allows incoming HTTP/WS traffic from local network devices (web dashboard and mobile app)"

Write-Output "[OK] Windows Firewall rule configured for port 8000 (Private profile)."
