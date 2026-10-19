import hashlib
import hmac
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from . import database as db
from . import settings


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'{salt}:{key}'


def check_password(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


def stable_device_id(installation_id: str) -> str:
    return f"dev_{hashlib.sha256(installation_id.encode('utf-8')).hexdigest()[:12]}"


def stable_camera_id(installation_id: str) -> str:
    return f"cam_{hashlib.sha256(installation_id.encode('utf-8')).hexdigest()[:12]}"


def _parse_seed_accounts() -> list[tuple[str, str, str]]:
    raw = os.getenv(
        'SEED_ACCOUNTS',
        'admin1@safespace.com:admin123:Admin 1,admin2@safespace.com:admin123:Admin 2',
    )
    accounts: list[tuple[str, str, str]] = []
    for entry in raw.split(','):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(':')
        if len(parts) >= 2:
            email = parts[0].strip().lower()
            pw = parts[1].strip()
            display_name = parts[2].strip() if len(parts) >= 3 else email.split('@')[0].title()
            if email and pw:
                accounts.append((email, pw, display_name))
    # Support legacy tests that explicitly set INITIAL_ADMIN_USERNAME in os.environ
    legacy_email = os.getenv('INITIAL_ADMIN_USERNAME')
    legacy_password = os.getenv('INITIAL_ADMIN_PASSWORD')
    if legacy_email and legacy_password:
        le = legacy_email.strip().lower()
        if all(a[0] != le for a in accounts):
            accounts.append((le, legacy_password, 'Admin'))
    return accounts


def bootstrap():
    accounts = _parse_seed_accounts()
    if not accounts:
        raise RuntimeError('Configure SEED_ACCOUNTS in .env')
    allowed_emails = {a[0] for a in accounts}
    with db.connection() as con:
        for email, password, display_name in accounts:
            existing = con.execute('SELECT id, password FROM users WHERE email=?', (email,)).fetchone()
            if existing:
                con.execute(
                    'UPDATE users SET display_name=?, disabled=0, role=? WHERE id=?',
                    (display_name, 'admin', existing['id']),
                )
            else:
                con.execute(
                    'INSERT INTO users(id, email, password, created_at, display_name, disabled, role) VALUES(?,?,?,?,?,?,?)',
                    (uuid.uuid4().hex, email, password_hash(password), now(), display_name, 0, 'admin'),
                )
        # Disable any non-seed accounts (e.g. legacy admin@gmail.com when not in active seed list)
        rows = con.execute('SELECT id, email FROM users').fetchall()
        for row in rows:
            if row['email'].lower() not in allowed_emails:
                con.execute('UPDATE users SET disabled=1 WHERE id=?', (row['id'],))
                con.execute('DELETE FROM sessions WHERE user_id=?', (row['id'],))


def create_session(
    user_id: str,
    name: str,
    installation_id: str | None = None,
    scope: str = 'admin',
    role: str = 'control',
    days: int | None = None,
):
    token = secrets.token_urlsafe(48)
    device = stable_device_id(installation_id) if installation_id else uuid.uuid4().hex
    if days is None:
        days = settings.CAMERA_TOKEN_DAYS if scope == 'camera' else settings.ADMIN_TOKEN_DAYS
    expires = time.time() + days * 86400
    with db.connection() as con:
        con.execute(
            'INSERT INTO sessions(token, user_id, device_id, name, expires, created_at, scope, role) VALUES(?,?,?,?,?,?,?,?)',
            (digest(token), user_id, device, name, expires, now(), scope, role),
        )
    return token, device


def session_for(token: str):
    if not token:
        return None
    token_hash = digest(token)
    now_ts = time.time()
    with db.connection() as con:
        row = con.execute(
            '''SELECT s.*, u.email, u.display_name, u.disabled, u.created_at AS user_created
               FROM sessions s
               LEFT JOIN users u ON s.user_id = u.id
               WHERE s.token = ? AND s.expires > ?''',
            (token_hash, now_ts),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        scope = d.get('scope') or 'admin'
        if scope == 'admin':
            if not d.get('email') or d.get('disabled'):
                return None
            # Sliding 30-day expiry refresh when more than 1 hour has elapsed
            new_expires = now_ts + settings.ADMIN_TOKEN_DAYS * 86400
            if new_expires - d['expires'] > 3600:
                con.execute('UPDATE sessions SET expires=? WHERE token=?', (new_expires, token_hash))
                d['expires'] = new_expires
        elif scope == 'camera':
            d.setdefault('email', f"{d.get('device_id', 'camera')}@camera.local")
            d.setdefault('user_created', d.get('created_at', now()))
        return d


def extract_token(request: Request) -> str:
    header = request.headers.get('authorization', '')
    if header.startswith('Bearer '):
        return header[7:].strip()
    return request.cookies.get('safespace_session', '')


async def authenticated_any_scope(request: Request):
    header = request.headers.get('authorization', '')
    token = extract_token(request)
    session = session_for(token) if token else None
    if not session:
        raise HTTPException(401, 'Sign in to continue')
    if not header and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        from .settings import ALLOWED_ORIGINS
        origin = request.headers.get('origin')
        from .network_policy import public_origin
        same_origin = public_origin(request)
        if origin and origin not in ALLOWED_ORIGINS and origin != same_origin:
            raise HTTPException(403, 'Origin not allowed')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Cross-site request not allowed')
    request.state.session = session
    return session


async def authenticated(request: Request):
    """Require an authenticated admin session. Rejects camera-scoped tokens with 403 Forbidden."""
    session = await authenticated_any_scope(request)
    if (session.get('scope') or 'admin') != 'admin':
        raise HTTPException(403, 'Camera-scoped token is not permitted on admin endpoints')
    return session
