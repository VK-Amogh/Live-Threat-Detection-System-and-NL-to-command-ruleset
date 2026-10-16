"""List every violence/non-violence clip with its label and a leakage-safe split.

python scripts/violence/build_manifest.py
Sources: SCVD (Kaggle, CCTV, official train/test), Hockey Fights, Real Life Violence Situations (RLVS), and
RWF-2000 when downloaded (official train/val).  Sources without an official split are split by clip, 70/10/20.
Label 1 = violence (fights, assaults, weaponized violence); 0 = normal.
"""
import json
import random
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'storage/datasets/raw'
WORK = ROOT / 'storage/datasets/work/violence'
OUT = ROOT / 'storage/datasets/violence/manifest.json'
VIDEO = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.mpg', '.mpeg'}


def extract_zips(folder: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for archive in sorted(folder.rglob('*.zip')):
        marker = dest / f'.{archive.stem}.done'
        if marker.exists():
            continue
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (dest / name).resolve().is_relative_to(dest.resolve()):
                    raise ValueError(f'Unsafe path in {archive}')
            z.extractall(dest)
        marker.write_text('ok')


def videos(folder: Path):
    return sorted(p for p in folder.rglob('*') if p.suffix.lower() in VIDEO)


def number_of(path):
    digits = re.findall(r'\d+', Path(path).stem)
    return int(digits[0]) if digits else 0


def block_split(rows, seed, block=25, test=0.2, val=0.1):
    """Split by blocks of consecutive clip numbers.

    Neighbouring clips in these collections are cut from the same footage, so a per-clip random split leaks
    near-identical scenes into validation/test (validation AUC 0.998 vs held-out 0.72 on CCTV exposed this).
    Whole blocks go to one split instead; label classes are blocked separately so both stay balanced.
    """
    rng = random.Random(seed)
    for label in (0, 1):
        group = sorted((r for r in rows if r['label'] == label), key=lambda r: number_of(r['path']))
        for i in range(0, len(group), block):
            draw = rng.random()
            split = 'test' if draw < test else 'val' if draw < test + val else 'train'
            for r in group[i:i + block]:
                r['split'] = split
    return rows


def scvd():
    base = RAW / 'kaggle/scvd/SCVD/SCVD_converted'  # 3-6 s clips; *_sec_split is a 1-second re-cut of the same footage
    rows = []
    for path in videos(base):
        parts = [p.lower() for p in path.parts]
        label = 0 if 'normal' in parts or any('normal' in p for p in parts[-3:]) else 1 if any(k in ' '.join(parts[-4:]) for k in ('violence', 'weapon')) else None
        if label is None:
            continue
        split = 'test' if 'test' in parts else 'train'
        rows.append({'path': str(path), 'label': label, 'split': split, 'dataset': 'SCVD (CCTV)'})
    # No official validation split: carve blocks of consecutive training clips (see block_split).
    train = [r for r in rows if r['split'] == 'train']
    block_split(train, 1, block=10, test=0.0, val=0.12)
    return rows


def hockey():
    folder = RAW / '34data__hockey-fight-videos'
    if not folder.exists():
        return []
    work = WORK / 'hockey'
    extract_zips(folder, work)
    rows = [{'path': str(p), 'label': 0 if p.stem.lower().startswith('no') else 1, 'dataset': 'Hockey fights'} for p in videos(work)]
    return block_split(rows, 2)


def rlvs():
    folder = RAW / '34data__real-life-violence'
    if not folder.exists():
        return []
    work = WORK / 'rlvs'
    extract_zips(folder, work)
    rows = [{'path': str(p), 'label': 0 if p.stem.upper().startswith('NV') or 'non' in ' '.join(p.parts).lower() else 1, 'dataset': 'Real Life Violence Situations'} for p in videos(work)]
    return block_split(rows, 3, block=40)


def rwf():
    base = ROOT / 'storage/datasets/work/rwf2000'
    rows = []
    for path in videos(base) if base.exists() else []:
        parts = [p.lower() for p in path.parts]
        rows.append({'path': str(path), 'label': 1 if 'fight' in parts else 0, 'split': 'train' if 'train' in parts else 'test', 'dataset': 'RWF-2000 (surveillance)'})
    train = [r for r in rows if r['split'] == 'train']
    block_split(train, 4, block=20, test=0.0, val=0.1)
    return rows


def stills():
    """Threat-free still images as 1-frame 'clips'.

    Without these the recogniser only ever saw people-in-video and fired (confidence 1.0) on fire scenes.
    Fire/smoke pictures, CCTV background frames and hard-negative web images are all non-violent;
    images containing a gun or knife are excluded (a posed weapon is not a fight, and the weapon detector owns it).
    Splits inherit the detection datasets' leakage-controlled splits.
    """
    rng = random.Random(11)
    quota = {'train': 1800, 'val': 150, 'test': 300}
    rows = []
    for domain, need_empty in (('fire_smoke', False), ('weapons', True)):
        root = ROOT / 'storage/datasets' / domain
        for split, count in quota.items():
            files = sorted((root / 'images' / split).glob('*.jpg'))
            if need_empty:
                files = [f for f in files if not (root / 'labels' / split / (f.stem + '.txt')).read_text().strip()]
            rng.shuffle(files)
            for f in files[: count if not need_empty else count // 2]:
                rows.append({'path': str(f), 'label': 0, 'split': split, 'dataset': 'Threat-free stills (fire scenes, CCTV, hard negatives)'})
    return rows


def main():
    rows = scvd() + hockey() + rlvs() + rwf() + stills()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    from collections import Counter
    print(len(rows), 'clips')
    print(Counter((r['dataset'], r['split'], r['label']) for r in rows))


if __name__ == '__main__':
    main()
