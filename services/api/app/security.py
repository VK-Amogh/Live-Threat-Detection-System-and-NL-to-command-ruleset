import hashlib
import hmac
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from . import database as db


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


def bootstrap():
    email = os.getenv('INITIAL_ADMIN_USERNAME')
    password = os.getenv('INITIAL_ADMIN_PASSWORD')
    with db.connection() as con:
        if not con.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            if not email or not password:
                raise RuntimeError('Set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD in .env')
            con.execute('INSERT INTO users VALUES(?,?,?,?)', (uuid.uuid4().hex, email.lower(), password_hash(password), now()))


def create_session(user_id, name):
    token = secrets.token_urlsafe(48)
    device = uuid.uuid4().hex
    with db.connection() as con:
        con.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', (digest(token), user_id, device, name, time.time()+7*86400, now()))
    return token, device


def session_for(token):
    with db.connection() as con:
        row = con.execute('SELECT s.*,u.email,u.created_at AS user_created FROM sessions s JOIN users u ON s.user_id=u.id WHERE token=? AND expires>?', (digest(token), time.time())).fetchone()
    return dict(row) if row else None


async def authenticated(request: Request):
    header = request.headers.get('authorization', '')
    token = header[7:] if header.startswith('Bearer ') else request.cookies.get('safespace_session', '')
    session = session_for(token) if token else None
    if not session:
        raise HTTPException(401, 'Sign in to continue')
    # Cookie-based mutations require an explicitly allowed browser origin.
    if not header and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        from .settings import ALLOWED_ORIGINS
        origin = request.headers.get('origin')
        same_origin = str(request.base_url).rstrip('/')
        if origin and origin not in ALLOWED_ORIGINS and origin != same_origin:
            raise HTTPException(403, 'Origin not allowed')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Cross-site request not allowed')
    request.state.session = session
    return session
