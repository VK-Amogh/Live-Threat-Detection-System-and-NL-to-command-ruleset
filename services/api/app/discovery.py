"""UDP discovery responder (port 47800) so devices re-find the laptop when DHCP changes its address.

Who gets an answer is decided by the route of the sender (config/network.yaml):
  trusted_lan  answered openly (your own hotspot);
  ibus_lan     answered only if the query carries an HMAC proof of the shared secret, so the server is never
               announced to strangers on an open network;
  anything else is ignored.
The reply is unicast to the sender and carries the signed route list for the sender's own network.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque

from . import settings
from .network_policy import policy, route_document, verify_discovery

logger = logging.getLogger(__name__)
REPLIES: dict[str, deque] = defaultdict(deque)
MAX_REPLIES_PER_SECOND = 5


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def reply_for(self, data: bytes, sender: str) -> bytes | None:
        """The datagram to send back, or None to stay silent. Pure so it can be tested without a socket."""
        try:
            payload = json.loads(data[:1024].decode('utf-8', errors='ignore'))
        except ValueError:
            return None
        if not isinstance(payload, dict) or payload.get('op') != 'discover' or payload.get('app') not in (None, 'safespace'):
            return None
        if payload.get('server_id') not in (None, settings.SERVER_ID):
            return None
        classified = policy().classify(sender, {}, 'http', '', enforce_tls=False)
        if not classified.allowed or classified.caps is None:
            return None
        mode = classified.caps.discovery
        if mode == 'none' or (mode == 'authenticated' and not verify_discovery(payload)):
            return None
        bucket = REPLIES[sender]
        now_ts = time.monotonic()
        while bucket and now_ts - bucket[0] > 1.0:
            bucket.popleft()
        if len(bucket) >= MAX_REPLIES_PER_SECOND:
            return None
        bucket.append(now_ts)
        document = route_document(only_route=classified.route)
        return json.dumps({'op': 'announce', 'v': 1, 'app': 'safespace', 'name': settings.SERVER_NAME,
                           'route': classified.route, **document}).encode('utf-8')

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        reply = self.reply_for(data, addr[0])
        if reply is not None and self.transport:
            self.transport.sendto(reply, addr)


async def start_discovery_server() -> asyncio.DatagramTransport | None:
    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: DiscoveryProtocol(), local_addr=('0.0.0.0', settings.DISCOVERY_PORT), allow_broadcast=True)
        logger.info('SafeSpace UDP discovery responder listening on 0.0.0.0:%d', settings.DISCOVERY_PORT)
        return transport
    except OSError as exc:
        logger.warning('Could not bind UDP discovery port %d: %s', settings.DISCOVERY_PORT, exc)
        return None
