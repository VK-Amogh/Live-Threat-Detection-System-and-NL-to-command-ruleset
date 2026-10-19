"""Automatically download production model weights from GitHub Releases.

Usage:
    python scripts/download_models.py
"""
import io
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = "VK-Amogh/Live-Threat-Detection-System-and-NL-to-command-ruleset"
RELEASE_TAG = "v1.0.0"

def main():
    print(f"Fetching release assets for {REPO} ({RELEASE_TAG})...")
    api_url = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}"
    headers = {"User-Agent": "SafeSpace-Downloader"}
    
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        print(f"Error fetching release info: {exc}", file=sys.stderr)
        return 1

    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    
    # 1. If zip bundle is available, prefer downloading and unzipping it
    zip_name = f"safespace-models-{RELEASE_TAG}.zip"
    if zip_name in assets:
        url = assets[zip_name]
        print(f"Downloading all-in-one weights bundle: {zip_name}...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
        print(f"Extracting {len(content) / 1e6:.1f} MB into repository...")
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(ROOT)
        print("Models successfully installed!")
        return 0

    # 2. Otherwise download individual assets
    (ROOT / "storage/models").mkdir(parents=True, exist_ok=True)
    (ROOT / "weights").mkdir(parents=True, exist_ok=True)

    for name, url in assets.items():
        if name.endswith(".zip"):
            continue
        dest = ROOT / "storage/models" / name if ("weapons" in name or "verifier" in name or "violence" in name or "crime" in name or "fire" in name) else ROOT / "weights" / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"Already present: {dest.name}")
            continue
        print(f"Downloading {name} -> {dest.relative_to(ROOT)}...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            dest.write_bytes(resp.read())

    print("All weights verified and downloaded successfully!")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
