"""Compatibility names for the previous hotspot-only lock.

The lock is now `network_policy` (route-aware, configured in config/network.yaml). `NETWORK_MODE=hotspot_only`
reproduces the old behaviour. Client-supplied SSID/BSSID values are no longer a security control: they are
spoofable, and reading the SSID on Android needs a location permission.
"""
from .network_policy import (  # noqa: F401
    check_request_allowed,
    check_websocket_allowed,
    classify_request,
    client_ip,
    get_host_wifi_status,
    require_capability,
)
