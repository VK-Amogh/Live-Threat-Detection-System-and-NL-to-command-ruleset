"""Publish v1.0.0 release to GitHub and upload all neural network model weights."""
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def get_token():
    cred_file = Path.home() / '.git-credentials'
    if cred_file.exists():
        for line in cred_file.read_text().splitlines():
            if 'github.com' in line and 'VK-Amogh' in line:
                parsed = urllib.parse.urlparse(line)
                if parsed.password:
                    return parsed.password
    token = os.getenv('GITHUB_TOKEN')
    if token:
        return token
    raise RuntimeError('GitHub token not found in ~/.git-credentials or GITHUB_TOKEN')

def make_request(url, method='GET', data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode()) if resp.headers.get_content_type() == 'application/json' else resp.read()

def main():
    token = get_token()
    repo = 'VK-Amogh/Live-Threat-Detection-System-and-NL-to-command-ruleset'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'SafeSpace-Release-Publisher'
    }

    tag = 'v1.0.0'
    release_name = 'SafeSpace v1.0.0 — Production Model Weights & Ruleset'
    release_body = (
        "## SafeSpace Threat Detection Models & Calibrated Weights\n\n"
        "This release contains pre-trained neural network weights, DINOv2 crop verifiers, "
        "VideoMAE motion heads, and calibration sidecars for the SafeSpace live threat detection system.\n\n"
        "### Included Model Weights:\n"
        "- **`weapons.pt`** (20.3 MB): YOLO26s object detector for weapons (`gun`, `knife`) calibrated for CCTV angles.\n"
        "- **`verifier.pt`** (6.6 MB): DINOv2-based false-positive suppressor re-scoring bounding box crops.\n"
        "- **`violence_head.pt`** (11.9 MB): DINOv2 temporal scene head for physical fight and violence detection.\n"
        "- **`violence_videomae.pt`** (1.2 MB): VideoMAE motion head for short-clip spatiotemporal dynamics.\n"
        "- **`yolo26n-pose.pt`** (7.9 MB): Pose estimator for person tracking and skeleton-based rule validation.\n"
        "- **`yolo26s.pt` / `yolo26n.pt` / `yolo11s.pt`**: Base YOLO detection models.\n"
        "- **`safespace-models-v1.0.0.zip`**: All-in-one bundle containing all weights and JSON calibration sidecars.\n\n"
        "### Automated Download:\n"
        "Run `python scripts/download_models.py` in the repository root to fetch and verify these weights automatically."
    )

    # 1. Create or get existing release
    releases_url = f'https://api.github.com/repos/{repo}/releases'
    status, releases = make_request(releases_url, headers=headers)
    release = None
    for r in releases:
        if r.get('tag_name') == tag:
            release = r
            print(f'Found existing release for {tag}: {release["html_url"]}')
            break

    if not release:
        payload = json.dumps({
            'tag_name': tag,
            'target_commitish': 'main',
            'name': release_name,
            'body': release_body,
            'draft': False,
            'prerelease': False
        }).encode('utf-8')
        h = dict(headers, **{'Content-Type': 'application/json'})
        status, release = make_request(releases_url, method='POST', data=payload, headers=h)
        print(f'Created new release {tag}: {release["html_url"]}')

    upload_url_template = release['upload_url']
    base_upload_url = upload_url_template.split('{')[0]

    # Existing assets
    existing_assets = {a['name']: a['id'] for a in release.get('assets', [])}

    # 2. Build all-in-one zip
    zip_path = ROOT / 'safespace-models-v1.0.0.zip'
    print('Creating safespace-models-v1.0.0.zip...')
    files_to_zip = [
        ROOT / 'storage/models/weapons.pt',
        ROOT / 'storage/models/weapons.json',
        ROOT / 'storage/models/verifier.pt',
        ROOT / 'storage/models/verifier.json',
        ROOT / 'storage/models/violence_head.pt',
        ROOT / 'storage/models/violence_head.json',
        ROOT / 'storage/models/violence_videomae.pt',
        ROOT / 'storage/models/violence_videomae.json',
        ROOT / 'storage/models/violence_ensemble.json',
        ROOT / 'weights/yolo26n-pose.pt',
        ROOT / 'weights/yolo26s.pt',
        ROOT / 'weights/yolo26n.pt',
        ROOT / 'weights/yolo11s.pt',
    ]

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files_to_zip:
            if f.is_file():
                arcname = str(f.relative_to(ROOT))
                zf.write(f, arcname)
    print(f'Created zip ({zip_path.stat().st_size / 1e6:.1f} MB)')

    # Files to upload individually
    assets_to_upload = [
        ROOT / 'storage/models/weapons.pt',
        ROOT / 'storage/models/weapons.json',
        ROOT / 'storage/models/verifier.pt',
        ROOT / 'storage/models/verifier.json',
        ROOT / 'storage/models/violence_head.pt',
        ROOT / 'storage/models/violence_head.json',
        ROOT / 'storage/models/violence_videomae.pt',
        ROOT / 'storage/models/violence_videomae.json',
        ROOT / 'storage/models/violence_ensemble.json',
        ROOT / 'weights/yolo26n-pose.pt',
        ROOT / 'weights/yolo26s.pt',
        ROOT / 'weights/yolo26n.pt',
        ROOT / 'weights/yolo11s.pt',
        zip_path,
    ]

    for asset_path in assets_to_upload:
        if not asset_path.is_file():
            print(f'Skipping missing file: {asset_path}')
            continue
        asset_name = asset_path.name
        if asset_name in existing_assets:
            print(f'Asset {asset_name} already exists in release, skipping.')
            continue

        size_mb = asset_path.stat().st_size / 1e6
        print(f'Uploading {asset_name} ({size_mb:.1f} MB)...')
        data = asset_path.read_bytes()
        upload_url = f'{base_upload_url}?name={urllib.parse.quote(asset_name)}'
        upload_headers = dict(headers, **{
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(len(data))
        })
        try:
            req = urllib.request.Request(upload_url, data=data, headers=upload_headers, method='POST')
            with urllib.request.urlopen(req) as resp:
                print(f'  -> Uploaded {asset_name} successfully!')
        except Exception as exc:
            print(f'  -> Failed to upload {asset_name}: {exc}')

    if zip_path.exists():
        zip_path.unlink()
    print('\nRelease process completed!')
    print(f'Release URL: {release["html_url"]}')

if __name__ == '__main__':
    main()
