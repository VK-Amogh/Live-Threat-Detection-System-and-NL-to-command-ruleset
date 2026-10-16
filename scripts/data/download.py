"""Download open datasets from Hugging Face into storage/datasets/raw (resumable).

python scripts/data/download.py <repo_id> [glob ...]
"""
import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'storage/datasets/raw'

if __name__ == '__main__':
    repo, patterns = sys.argv[1], sys.argv[2:] or None
    print('>>', repo, patterns, flush=True)
    snapshot_download(repo, repo_type='dataset', local_dir=str(RAW / repo.replace('/', '__')), allow_patterns=patterns, max_workers=int(os.environ.get('DL_WORKERS', '32')))
    print('DONE', flush=True)
