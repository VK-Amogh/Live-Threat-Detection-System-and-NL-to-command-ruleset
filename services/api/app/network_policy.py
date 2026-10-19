"""Route-aware network policy.

Every request is classified by the TCP peer address (never by client-supplied headers such as an SSID) into one
route: loopback, trusted_lan (your own hotspot), ibus_lan (the open iBus Wi-Fi), tailnet (Tailscale) or relay
(a reverse proxy you operate). Which routes are accepted depends on NETWORK_MODE, and each route carries its own
rules: whether the baked password / enrollment code may be used, whether HTTPS is mandatory, and whether the
discovery beacon answers. Configuration lives in config/network.yaml.

Identity (device tokens), not the network, is the security boundary. The route only ever *restricts* further.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import psutil
import yaml
from fastapi import HTTPException, Request, WebSocket

from . import settings

CONFIG_PATH = Path(os.getenv('NETWORK_CONFIG', str(settings.ROOT / 'config' / 'network.yaml')))
ENV_KEYS = ('NETWORK_MODE', 'TRUSTED_LAN_CIDRS', 'IBUS_CIDRS', 'TAILNET_CIDRS', 'TRUSTED_PROXIES', 'IBUS_PASSWORD_LOGIN')
FORWARD_HEADERS = ('x-forwarded-for', 'forwarded', 'x-real-ip', 'cf-connecting-ip', 'x-forwarded-host')
CIDR_ROUTES = ('loopback', 'trusted_lan', 'tailnet', 'ibus_lan')   # matched by peer address; relay is matched by peer being a proxy
MESSAGES = {
    'password_login': 'Password sign-in is turned off on {label}. Pair this device with a link or code from the dashboard.',
    'enroll': 'Camera enrollment with the built-in code is turned off on {label}. Pair this phone with a camera link from the dashboard.',
}


@dataclass(frozen=True)
class Capabilities:
    password_login: bool
    enroll: bool
    discovery: str      # none | open | authenticated
    require_tls: bool
    ladder: str         # full | reduced

    def as_dict(self) -> dict[str, Any]:
        return {'password_login': self.password_login, 'enroll': self.enroll, 'discovery': self.discovery,
                'require_tls': self.require_tls, 'ladder': self.ladder}


@dataclass(frozen=True)
class Classified:
    route: str | None
    label: str
    peer: str
    client_ip: str
    scheme: str
    host: str
    via_proxy: bool
    caps: Capabilities | None
    reason: str | None

    @property
    def allowed(self) -> bool:
        return self.route is not None and self.reason is None


def normalize_ip(raw: str | None) -> str:
    if not raw:
        return ''
    host = raw.strip()
    if host == 'testclient':
        return '127.0.0.1'      # Starlette's TestClient peer
    if host.startswith('::ffff:'):
        host = host[7:]
    if '%' in host:
        host = host.split('%', 1)[0]
    return host


def _networks(values) -> list:
    out = []
    for value in values or []:
        try:
            out.append(ipaddress.ip_network(str(value).strip(), strict=False))
        except ValueError:
            continue
    return out


def _csv_env(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, '').split(',') if x.strip()]


class NetworkPolicy:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        modes = config['modes']
        mode = os.getenv('NETWORK_MODE') or config.get('mode', 'ibus')
        if mode not in modes:
            raise ValueError(f"NETWORK_MODE '{mode}' is not one of {sorted(modes)}")
        self.mode = mode
        self.enabled = tuple(modes[mode])
        profiles = config['profiles']
        self.labels = {name: profiles.get(name, {}).get('label', name) for name in set(profiles) | {'relay'}}
        extra = {'trusted_lan': _csv_env('TRUSTED_LAN_CIDRS'), 'ibus_lan': _csv_env('IBUS_CIDRS'), 'tailnet': _csv_env('TAILNET_CIDRS')}
        self.cidrs = {name: _networks(profiles.get(name, {}).get('cidrs', []) + extra.get(name, [])) for name in CIDR_ROUTES}
        self.proxies = _networks(profiles.get('relay', {}).get('proxies', []) + _csv_env('TRUSTED_PROXIES'))
        self.reject_forwarded = bool(config.get('loopback_rejects_forwarded', True))
        self.caps: dict[str, Capabilities] = {}
        for name, raw in config['capabilities'].items():
            self.caps[name] = Capabilities(bool(raw['password_login']), bool(raw['enroll']), str(raw['discovery']),
                                           bool(raw['require_tls']), str(raw.get('ladder', 'full')))
        if os.getenv('IBUS_PASSWORD_LOGIN', '').lower() == 'true':
            ib = self.caps['ibus_lan']
            self.caps['ibus_lan'] = Capabilities(True, ib.enroll, ib.discovery, ib.require_tls, ib.ladder)

    def route_for_ip(self, ip) -> str | None:
        for name in CIDR_ROUTES:
            if any(ip in net for net in self.cidrs[name]):
                return name
        return None

    def classify(self, peer: str | None, headers: Mapping[str, str], scheme: str = 'http', host: str = '',
                 enforce_tls: bool = True) -> Classified:
        peer_ip = normalize_ip(peer)

        def reject(reason: str, route: str | None = None, client: str = '') -> Classified:
            return Classified(route, self.labels.get(route or '', 'Unknown network'), peer_ip, client or peer_ip, scheme, host,
                              False, None, reason)

        try:
            ip = ipaddress.ip_address(peer_ip)
        except ValueError:
            return reject('This network is not allowed to reach SafeSpace.')

        via_proxy = any(ip in net for net in self.proxies)
        client_ip = peer_ip
        if via_proxy:
            route = 'relay'
            hops = [h.strip() for h in (headers.get('x-forwarded-for') or '').split(',') if h.strip()]
            client = None
            for hop in reversed(hops):
                try:
                    hop_ip = ipaddress.ip_address(normalize_ip(hop))
                except ValueError:
                    return reject('The relay sent a malformed client address.', route)
                if not any(hop_ip in net for net in self.proxies):
                    client = str(hop_ip)
                    break
            if client is None:
                return reject('The relay did not forward the client address.', route)
            client_ip = client
            proto = (headers.get('x-forwarded-proto') or 'http').split(',')[0].strip().lower()
            scheme = 'https' if proto == 'https' else 'http'
            host = (headers.get('x-forwarded-host') or host or '').split(',')[0].strip()
        else:
            route = self.route_for_ip(ip)
            if route == 'loopback' and self.reject_forwarded and any(headers.get(h) for h in FORWARD_HEADERS):
                return reject('Requests forwarded through an unknown local proxy are not trusted.', 'loopback')
            if route is None:
                return reject('This network is not allowed to reach SafeSpace.')
        label = self.labels.get(route, route)
        if route not in self.enabled:
            return Classified(route, label, peer_ip, client_ip, scheme, host, via_proxy, None,
                              f"{label} is not enabled (network mode '{self.mode}').")
        caps = self.caps[route]
        if enforce_tls and caps.require_tls and scheme != 'https':
            return Classified(route, label, peer_ip, client_ip, scheme, host, via_proxy, caps,
                              f'{label} requires an encrypted connection. Use https (port {settings.HTTPS_PORT}).')
        return Classified(route, label, peer_ip, client_ip, scheme, host, via_proxy, caps, None)


_POLICY: dict[str, Any] = {'sig': None, 'policy': None, 'checked': 0.0}


def policy() -> NetworkPolicy:
    """The active policy; reloads when config/network.yaml or one of the NETWORK_* variables changes."""
    now_ts = time.monotonic()
    env_sig = tuple(os.getenv(k) for k in ENV_KEYS)
    if _POLICY['policy'] is not None and env_sig == _POLICY['sig'][1] and now_ts - _POLICY['checked'] < 2.0:
        return _POLICY['policy']
    try:
        mtime = CONFIG_PATH.stat().st_mtime_ns
    except OSError:
        mtime = 0
    sig = (mtime, env_sig)
    _POLICY['checked'] = now_ts
    if _POLICY['policy'] is None or sig != _POLICY['sig']:
        _POLICY['policy'] = NetworkPolicy(yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8')))
        _POLICY['sig'] = sig
    return _POLICY['policy']


# --- request / websocket helpers -------------------------------------------------------------------------------------

def classify_request(request: Request) -> Classified:
    cached = getattr(request.state, 'net', None)
    if cached is not None:
        return cached
    peer = request.client.host if request.client else None
    result = policy().classify(peer, request.headers, request.url.scheme, request.headers.get('host', ''))
    request.state.net = result
    return result


def client_ip(request: Request) -> str:
    """The real client address: the TCP peer, or the relay-forwarded address when the peer is a trusted relay."""
    return classify_request(request).client_ip


def public_origin(request: Request) -> str:
    c = classify_request(request)
    return f"{c.scheme}://{c.host}".rstrip('/')


def check_request_allowed(request: Request) -> None:
    c = classify_request(request)
    if not c.allowed:
        raise HTTPException(403, c.reason)
    if request.url.path.startswith('/api/v1/internal') and c.route != 'loopback':
        raise HTTPException(404, 'Not found')


def require_capability(request: Request, capability: str) -> Classified:
    c = classify_request(request)
    if not c.allowed or not getattr(c.caps, capability, False):
        raise HTTPException(403, MESSAGES[capability].format(label=c.label) if c.allowed else c.reason)
    return c


def requires(capability: str):
    """FastAPI dependency: refuse a route that may not do this BEFORE the request body is even validated."""
    async def dependency(request: Request) -> None:
        check_request_allowed(request)
        require_capability(request, capability)
    return dependency


async def check_websocket_allowed(ws: WebSocket) -> bool:
    scheme = 'https' if ws.url.scheme == 'wss' else 'http'
    c = policy().classify(ws.client.host if ws.client else None, ws.headers, scheme, ws.headers.get('host', ''))
    ws.state.net = c
    if not c.allowed:
        await ws.close(code=4403)
        return False
    return True


# --- server identity, signed route list, authenticated discovery -----------------------------------------------------

def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def hmac_hex(message: str) -> str:
    """HMAC-SHA256 of a plain string under the shared secret. Plain strings (not JSON) so every client computes the
    same bytes without agreeing on a JSON canonical form."""
    return hmac.new(settings.SERVER_PROOF_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


def identity_proof(nonce: str) -> str:
    return hmac_hex(f'id|{settings.SERVER_ID}|{nonce}')


def discovery_proof(ts: int) -> str:
    return hmac_hex(f'discover|{settings.SERVER_ID}|{int(ts)}')


def routes_signature(routes_json: str) -> str:
    return hmac_hex(f'routes|{routes_json}')


def verify_discovery(payload: dict[str, Any]) -> bool:
    try:
        ts = int(payload['ts'])
        proof = str(payload['proof'])
    except (KeyError, TypeError, ValueError):
        return False
    return abs(time.time() - ts) <= 120 and hmac.compare_digest(proof, discovery_proof(ts))


LISTENERS: dict[str, Any] = {'http': settings.HTTP_PORT, 'https': None, 'pins': []}


def set_listeners(http_port: int | None, https_port: int | None, pins: list[str] | None = None) -> None:
    LISTENERS.update(http=http_port, https=https_port, pins=list(pins or []))


def local_ipv4() -> list[tuple[str, str]]:
    found = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name != 'AF_INET':
                continue
            ip = addr.address
            if ip.startswith(('127.', '169.254.')):
                continue
            found.append((name, ip))
    return found


def advertised_routes() -> list[dict[str, Any]]:
    """The addresses a device can try, built from the laptop's live interfaces so DHCP changes are picked up."""
    p = policy()
    http_port, https_port = LISTENERS.get('http'), LISTENERS.get('https')
    routes: list[dict[str, Any]] = []
    for iface, ip in local_ipv4():
        route = p.route_for_ip(ipaddress.ip_address(ip))
        if route is None or route == 'loopback' or route not in p.enabled:
            continue
        caps = p.caps[route]
        label = p.labels.get(route, route)
        if http_port and not caps.require_tls:
            routes.append({'route': route, 'label': label, 'url': f'http://{ip}:{http_port}', 'tls': False, 'interface': iface})
        if https_port:
            routes.append({'route': route, 'label': label, 'url': f'https://{ip}:{https_port}', 'tls': True, 'interface': iface})
    tailnet_name = os.getenv('TAILNET_HOSTNAME', '').strip()
    if tailnet_name and 'tailnet' in p.enabled and http_port:
        routes.append({'route': 'tailnet', 'label': p.labels['tailnet'], 'url': f'http://{tailnet_name}:{http_port}', 'tls': False, 'interface': 'tailscale'})
    if 'relay' in p.enabled:
        for origin in [o for o in settings.ALLOWED_ORIGINS + settings.PUBLIC_SERVER_URLS if o.startswith('https://') and 'localhost' not in o and '127.0.0.1' not in o]:
            routes.append({'route': 'relay', 'label': p.labels['relay'], 'url': origin.rstrip('/'), 'tls': True, 'interface': 'relay'})
    for url in settings.PUBLIC_SERVER_URLS:
        if not any(r['url'] == url.rstrip('/') for r in routes):
            routes.append({'route': 'configured', 'label': 'Configured address', 'url': url.rstrip('/'), 'tls': url.startswith('https://'), 'interface': ''})
    return routes


def route_document(only_route: str | None = None) -> dict[str, Any]:
    """The address list a device can try, with an HMAC over its exact JSON text (`routes_json`), so the app can
    verify it came from the genuine server. `only_route` limits it to one route (a discovery caller's own network)."""
    routes = [r for r in advertised_routes() if only_route is None or r['route'] in (only_route, 'configured')]
    body = {'server_id': settings.SERVER_ID, 'routes': routes, 'pins': list(LISTENERS.get('pins') or [])}
    text = canonical(body)
    return {**body, 'routes_json': text, 'routes_sig': routes_signature(text)}


# --- truthful status for the System screens --------------------------------------------------------------------------

_SSID_CACHE: dict[str, Any] = {'ts': 0.0, 'value': None}


def host_wifi() -> dict[str, str | None]:
    """The Wi-Fi network the laptop is actually on (Windows only; None when unknown). Informational, never a gate."""
    if time.time() - _SSID_CACHE['ts'] < 8.0:
        return _SSID_CACHE['value'] or {'ssid': None, 'bssid': None}
    info: dict[str, str | None] = {'ssid': None, 'bssid': None}
    if sys.platform.startswith('win'):
        try:
            out = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], capture_output=True, text=True, timeout=2.0,
                                 creationflags=0x08000000).stdout
            for line in out.splitlines():
                if ':' not in line:
                    continue
                key, value = [part.strip() for part in line.split(':', 1)]
                if key == 'SSID' and not info['ssid']:
                    info['ssid'] = value or None
                elif key == 'AP BSSID' and not info['bssid']:
                    info['bssid'] = value.lower() or None
        except (OSError, subprocess.SubprocessError):
            pass
    _SSID_CACHE.update(ts=time.time(), value=info)
    return info


def network_status() -> dict[str, Any]:
    p = policy()
    interfaces = []
    for iface, ip in local_ipv4():
        route = p.route_for_ip(ipaddress.ip_address(ip))
        interfaces.append({'interface': iface, 'ip': ip, 'route': route, 'enabled': route in p.enabled if route else False})
    warnings = []
    https_up = bool(LISTENERS.get('https'))
    for item in interfaces:
        if item['enabled'] and p.caps[item['route']].require_tls and not https_up:
            warnings.append(f"{p.labels[item['route']]} is enabled but the HTTPS listener is not running, so devices there cannot connect.")
        if item['route'] is None:
            warnings.append(f"{item['ip']} ({item['interface']}) is not in any configured network, so devices on it are refused.")
    wifi = host_wifi()
    return {
        'mode': p.mode,
        'modes': sorted(p.config['modes']),
        'enabled_routes': list(p.enabled),
        'labels': {name: p.labels.get(name, name) for name in p.enabled},
        'capabilities': {name: p.caps[name].as_dict() for name in p.enabled},
        'cidrs': {name: [str(n) for n in nets] for name, nets in p.cidrs.items()},
        'listeners': {'http': LISTENERS.get('http'), 'https': LISTENERS.get('https')},
        'tls_pins': list(LISTENERS.get('pins') or []),
        'interfaces': interfaces,
        'routes': advertised_routes(),
        'host_ssid': wifi['ssid'],
        'host_bssid': wifi['bssid'],
        'warnings': warnings,
    }


def get_host_wifi_status(force: bool = False) -> dict[str, Any]:
    """Backward-compatible name used by existing screens; now reports what is true rather than a fixed hotspot."""
    status = network_status()
    return {
        'enforced': status['mode'] == 'hotspot_only',
        'mode': status['mode'],
        'detected_ssid': status['host_ssid'],
        'detected_bssid': status['host_bssid'],
        'local_ips': [i['ip'] for i in status['interfaces']],
        'host_verified': any(i['enabled'] for i in status['interfaces']),
        'allowed_subnets': status['cidrs'],
    }
