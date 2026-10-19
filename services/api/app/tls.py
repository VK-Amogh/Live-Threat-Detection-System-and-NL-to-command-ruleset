"""Local certificate authority and server certificate for the HTTPS listener.

Why this exists: iBus is an open Wi-Fi network, so anything not encrypted can be read by anyone nearby. The laptop
therefore serves HTTPS with a certificate from its own private CA, and the app trusts exactly that key.

* ca.key / ca.pem      - created once, valid ten years. ca.pem is public and is shipped inside the APK so Android's
                         own TLS stack (the video player) can verify the server.
* server.key           - created once and REUSED when the certificate is renewed, so the public-key pin baked into the
                         APK never changes.
* server.pem           - re-issued whenever the laptop's addresses change (DHCP) or it nears expiry, with every current
                         IPv4 address as a subject alternative name.
* pin                  - base64(SHA-256(SubjectPublicKeyInfo)) of server.pem. The Dart client compares it in
                         badCertificateCallback, so a changed IP never breaks a paired phone.

Certificates are made with the `openssl` command line tool (bundled with Git for Windows); nothing is downloaded.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import settings
from .network_policy import local_ipv4

CA_DAYS = 3650
SERVER_DAYS = 825
RENEW_BEFORE_S = 30 * 86400
OPENSSL_FALLBACKS = (
    r'C:\Program Files\Git\mingw64\bin\openssl.exe',
    r'C:\Program Files\Git\usr\bin\openssl.exe',
    r'C:\Program Files (x86)\Git\usr\bin\openssl.exe',
)


class TlsUnavailable(RuntimeError):
    pass


@dataclass
class TlsMaterial:
    cert: Path
    key: Path
    ca: Path
    pin: str
    sans: list[str]
    regenerated: bool


def openssl_exe() -> str:
    found = shutil.which('openssl')
    if found:
        return found
    for candidate in OPENSSL_FALLBACKS:
        if os.path.exists(candidate):
            return candidate
    raise TlsUnavailable('openssl was not found. Install Git for Windows (it bundles openssl) or add openssl to PATH.')


def _run(args: list[str], cwd: Path) -> None:
    flags = 0x08000000 if sys.platform.startswith('win') else 0
    result = subprocess.run([openssl_exe(), *args], cwd=cwd, capture_output=True, text=True, timeout=60, creationflags=flags)
    if result.returncode != 0:
        raise TlsUnavailable(f'openssl {args[0]} failed: {result.stderr.strip()[:300]}')


# --- public-key pin ---------------------------------------------------------------------------------------------------

def _tlv(buf: bytes, pos: int) -> tuple[int, int, int]:
    """(tag, content_start, content_length) of the DER element at `pos`."""
    tag = buf[pos]
    length = buf[pos + 1]
    start = pos + 2
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(buf[start:start + count], 'big')
        start += count
    return tag, start, length


def spki_der(cert_der: bytes) -> bytes:
    """The SubjectPublicKeyInfo element of an X.509 certificate (DER)."""
    _, pos, _ = _tlv(cert_der, 0)            # Certificate ::= SEQUENCE
    _, pos, _ = _tlv(cert_der, pos)          # tbsCertificate ::= SEQUENCE
    tag, start, length = _tlv(cert_der, pos)
    if tag == 0xA0:                          # [0] version (optional)
        pos = start + length
        tag, start, length = _tlv(cert_der, pos)
    pos = start + length                     # past serialNumber
    for _ in range(4):                       # signature, issuer, validity, subject
        _, start, length = _tlv(cert_der, pos)
        pos = start + length
    _, start, length = _tlv(cert_der, pos)   # subjectPublicKeyInfo
    return cert_der[pos:start + length]


def pin_of_der(cert_der: bytes) -> str:
    return base64.b64encode(hashlib.sha256(spki_der(cert_der)).digest()).decode('ascii')


def pin_of_pem(path: Path) -> str:
    return pin_of_der(ssl.PEM_cert_to_DER_cert(path.read_text(encoding='ascii')))


# --- certificates -----------------------------------------------------------------------------------------------------

def current_sans(extra: list[str] | None = None) -> list[str]:
    names = {'localhost', 'safespace.local'}
    try:
        names.add(socket.gethostname().lower())
    except OSError:
        pass
    ips = {'127.0.0.1'} | {ip for _, ip in local_ipv4()}
    for item in (extra or []) + [x.strip() for x in os.getenv('TLS_EXTRA_SANS', '').split(',') if x.strip()]:
        (ips if item.replace('.', '').isdigit() else names).add(item)
    return sorted(f'DNS:{n}' for n in names) + sorted(f'IP:{i}' for i in ips)


def _expires_soon(cert: Path) -> bool:
    try:
        flags = 0x08000000 if sys.platform.startswith('win') else 0
        out = subprocess.run([openssl_exe(), 'x509', '-noout', '-enddate', '-in', str(cert)], capture_output=True, text=True,
                             timeout=30, creationflags=flags).stdout.strip()          # notAfter=Oct 17 12:00:00 2028 GMT
        return ssl.cert_time_to_seconds(out.split('=', 1)[1]) - time.time() < RENEW_BEFORE_S
    except (OSError, subprocess.SubprocessError, IndexError, ValueError, TlsUnavailable):
        return True


def ensure_all(tls_dir: Path | None = None, extra_sans: list[str] | None = None) -> TlsMaterial:
    folder = Path(tls_dir or settings.TLS_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    ca_key, ca_pem = folder / 'ca.key', folder / 'ca.pem'
    key, cert, sans_file = folder / 'server.key', folder / 'server.pem', folder / 'server.sans.json'

    if not (ca_key.exists() and ca_pem.exists()):
        _run(['ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'ca.key'], folder)
        _run(['req', '-x509', '-new', '-key', 'ca.key', '-sha256', '-days', str(CA_DAYS),
              '-subj', '/CN=SafeSpace Local CA/O=SafeSpace',
              '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
              '-out', 'ca.pem'], folder)
        for stale in (cert, sans_file):
            stale.unlink(missing_ok=True)       # a new CA invalidates any previous server certificate
    if not key.exists():
        _run(['ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', 'server.key'], folder)
        cert.unlink(missing_ok=True)

    sans = current_sans(extra_sans)
    known = json.loads(sans_file.read_text()) if sans_file.exists() else None
    regenerated = False
    if not cert.exists() or known != sans or _expires_soon(cert):
        (folder / 'server.ext').write_text(
            'basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n'
            f"subjectAltName={','.join(sans)}\n", encoding='ascii')
        _run(['req', '-new', '-key', 'server.key', '-subj', '/CN=SafeSpace Server/O=SafeSpace', '-out', 'server.csr'], folder)
        _run(['x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial',
              '-out', 'server.pem', '-days', str(SERVER_DAYS), '-sha256', '-extfile', 'server.ext'], folder)
        sans_file.write_text(json.dumps(sans))
        regenerated = True
    return TlsMaterial(cert=cert, key=key, ca=ca_pem, pin=pin_of_pem(cert), sans=sans, regenerated=regenerated)
