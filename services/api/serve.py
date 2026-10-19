"""SafeSpace API launcher: HTTP and HTTPS from ONE process.

The event broadcast, camera hub and recorder live in this process's memory (decision D-003), so the encrypted listener
cannot be a second process. Two uvicorn servers share one event loop and one `app`:

    http   :8000   plain; routes that do not require TLS (your hotspot, Tailscale, this laptop)
    https  :8443   pinned-key TLS; the only listener the open iBus Wi-Fi is allowed to use

Which route may use which listener is decided per request by app/network_policy.py, not by the port.
The server certificate is re-issued (same key, so the app's pin stays valid) whenever the laptop's addresses change.

Run:  python services/api/serve.py        (scripts/start.ps1 does this)
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / 'contracts' / 'src', ROOT / 'services' / 'api', ROOT / 'services' / 'inference'):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import uvicorn  # noqa: E402

from app import network_policy, settings, tls  # noqa: E402

log = logging.getLogger('safespace.serve')
CERT_CHECK_S = 30


class Server(uvicorn.Server):
    """uvicorn installs signal handlers per server; with two in one process we install one set ourselves."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


def make_config(app, *, port: int, bind: str, lifespan: str, certfile: str | None = None, keyfile: str | None = None) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host=bind,
        port=port,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        lifespan=lifespan,
        proxy_headers=False,        # forwarded headers are interpreted only by network_policy, and only from declared relays
        server_header=False,
        log_level=os.getenv('LOG_LEVEL', 'info').lower(),
        ws_ping_interval=20,        # detect a phone that dropped off Wi-Fi without closing its socket
        ws_ping_timeout=20,
    )


async def watch_certificate(material: tls.TlsMaterial, config: uvicorn.Config) -> None:
    """Re-issue the server certificate when the laptop's addresses change and hot-load it into the live TLS context."""
    while True:
        await asyncio.sleep(CERT_CHECK_S)
        try:
            fresh = await asyncio.to_thread(tls.ensure_all)
            if fresh.regenerated and config.ssl is not None:
                config.ssl.load_cert_chain(str(fresh.cert), str(fresh.key))
                log.info('TLS certificate re-issued for %s', ', '.join(s for s in fresh.sans if s.startswith('IP:')))
        except Exception as exc:     # never let certificate upkeep take the server down
            log.warning('TLS certificate check failed: %s', exc)


async def run() -> None:
    from app.main import app

    http_port, https_port = settings.HTTP_PORT, settings.HTTPS_PORT
    http_bind = os.getenv('HTTP_BIND', '0.0.0.0')
    https_bind = os.getenv('HTTPS_BIND', '0.0.0.0')

    material: tls.TlsMaterial | None = None
    if settings.TLS_ENABLED:
        try:
            material = await asyncio.to_thread(tls.ensure_all)
        except tls.TlsUnavailable as exc:
            log.error('HTTPS is disabled: %s', exc)
    network_policy.set_listeners(http_port, https_port if material else None, [material.pin] if material else [])

    servers: list[Server] = [Server(make_config(app, port=http_port, bind=http_bind, lifespan='on'))]
    tls_config = None
    if material:
        tls_config = make_config(app, port=https_port, bind=https_bind, lifespan='off',
                                 certfile=str(material.cert), keyfile=str(material.key))
        servers.append(Server(tls_config))

    def stop(*_):
        for server in servers:
            server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, 'SIGBREAK', None)):
        if sig is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, stop)

    p = network_policy.policy()
    log.info('SafeSpace API: network mode "%s", routes %s', p.mode, ', '.join(p.enabled))
    log.info('Listening on http://%s:%d%s', http_bind, http_port,
             f' and https://{https_bind}:{https_port} (pin {material.pin})' if material else ' (HTTPS off)')

    tasks = [asyncio.create_task(server.serve()) for server in servers]
    watcher = None
    if material and tls_config is not None:
        watcher = asyncio.create_task(watch_certificate(material, tls_config))
    try:
        await asyncio.gather(*tasks)
    finally:
        if watcher:
            watcher.cancel()


def main() -> None:
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper(), format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    asyncio.run(run())


if __name__ == '__main__':
    main()
