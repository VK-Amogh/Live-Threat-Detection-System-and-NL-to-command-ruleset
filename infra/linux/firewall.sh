#!/usr/bin/env bash
# SafeSpace Linux UFW / iptables setup
# Restricts port 8000 to local subnet only

SUBNET=${1:-"192.168.1.0/24"}
sudo ufw allow from "$SUBNET" to any port 8000 proto tcp comment "SafeSpace API on LAN"
echo "[OK] Allowed LAN subnet $SUBNET on port 8000."
