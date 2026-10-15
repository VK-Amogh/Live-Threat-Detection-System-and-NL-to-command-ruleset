from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / '.env')
STORAGE = Path(os.getenv('SAFESPACE_STORAGE', str(ROOT / 'storage'))).resolve()
STORAGE.mkdir(parents=True, exist_ok=True)
for folder in ('media', 'uploads', 'logs'):
    (STORAGE / folder).mkdir(exist_ok=True)
DB_PATH = STORAGE / 'safespace.db'
INFERENCE_URL = os.getenv('INFERENCE_URL', 'http://127.0.0.1:8001')
INTERNAL_TOKEN = os.getenv('INTERNAL_SERVICE_TOKEN', '')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
ALLOWED_ORIGINS = [x.strip() for x in os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173').split(',')]
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '500')) * 1024 * 1024
