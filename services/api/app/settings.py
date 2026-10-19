from pathlib import Path
import os
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / '.env')
STORAGE = Path(os.getenv('SAFESPACE_STORAGE', str(ROOT / 'storage'))).resolve()
STORAGE.mkdir(parents=True, exist_ok=True)
for folder in ('media', 'uploads', 'logs', 'recordings', 'snapshots', 'exports', 'backups', 'dist'):
    (STORAGE / folder).mkdir(exist_ok=True)

DB_PATH = STORAGE / 'safespace.db'
INFERENCE_URL = os.getenv('INFERENCE_URL', 'http://127.0.0.1:8001')
INTERNAL_TOKEN = os.getenv('INTERNAL_SERVICE_TOKEN', '')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'


def _csv(name: str, default: str = '') -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(',') if x.strip()]


# Browser origins allowed to call the API cross-origin (the dashboard served by this API is same-origin and needs none).
# Add the relay's public origin here when NETWORK_MODE=anywhere.
ALLOWED_ORIGINS = _csv(
    'ALLOWED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000,https://localhost:8443,https://127.0.0.1:8443,'
    'http://localhost:5173,http://127.0.0.1:5173',
) + _csv('PUBLIC_ORIGINS')
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '500')) * 1024 * 1024

# v3 Server identity & discovery
SERVER_ID = os.getenv('SERVER_ID', 'ss-7f3c2a')
SERVER_NAME = os.getenv('SERVER_NAME', 'SafeSpace Laptop')
# Extra, fixed URLs to advertise besides the laptop's live interface addresses (e.g. a Tailscale name or relay origin).
PUBLIC_SERVER_URLS = _csv('PUBLIC_SERVER_URLS')
DISCOVERY_PORT = int(os.getenv('DISCOVERY_PORT', '47800'))

# Listeners (services/api/serve.py). HTTPS carries every route that needs encryption (see config/network.yaml).
HTTP_PORT = int(os.getenv('API_PORT', os.getenv('HTTP_PORT', '8000')))
HTTPS_PORT = int(os.getenv('HTTPS_PORT', '8443'))
TLS_ENABLED = os.getenv('TLS_ENABLED', 'true').lower() == 'true'
TLS_DIR = Path(os.getenv('TLS_DIR', str(STORAGE / 'tls'))).resolve()

# v3 Auth & enrollment. The enrollment code doubles as the shared secret that proves the server's identity
# to the app (HMAC challenge) and authenticates discovery on open networks; rotate it by rebuilding the APK.
CAMERA_ENROLLMENT_CODE = os.getenv('CAMERA_ENROLLMENT_CODE', 'ss-enroll-np4a-7495-9f8e7d6c5b4a3210')
SERVER_PROOF_KEY = os.getenv('SERVER_PROOF_KEY') or CAMERA_ENROLLMENT_CODE
ADMIN_TOKEN_DAYS = int(os.getenv('ADMIN_TOKEN_DAYS', '30'))
CAMERA_TOKEN_DAYS = int(os.getenv('CAMERA_TOKEN_DAYS', '365'))
DEMO_AUTOFILL_PASSWORD = os.getenv('DEMO_AUTOFILL_PASSWORD', 'true').lower() == 'true'


def active_storage() -> Path:
    """Return the active storage path, respecting test monkeypatching of main.STORAGE."""
    main_mod = sys.modules.get('app.main')
    base = getattr(main_mod, 'STORAGE', STORAGE) if main_mod else STORAGE
    base = Path(base)
    for folder in ('media', 'uploads', 'logs', 'recordings', 'snapshots', 'exports', 'backups', 'dist'):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base
