"""Short-lived, single-use WebSocket tickets (D-014): a ticket stands in for a session token on a socket handshake."""
from __future__ import annotations

import secrets
import time

TICKETS: dict[str, tuple[float, str]] = {}   # ticket -> (expires_at, session token)
TTL_S = 30


def issue(session_token: str) -> str:
    now_ts = time.time()
    for key, (expires, _) in list(TICKETS.items()):
        if expires < now_ts:
            TICKETS.pop(key, None)
    ticket = secrets.token_urlsafe(32)
    TICKETS[ticket] = (now_ts + TTL_S, session_token)
    return ticket


def redeem(ticket: str) -> str | None:
    """The session token behind a valid ticket (consuming it), or None."""
    entry = TICKETS.pop(ticket, None)
    if not entry or entry[0] < time.time():
        return None
    return entry[1]
