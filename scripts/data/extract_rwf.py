"""Extract RWF-2000 from the Hugging Face 7z archive (videos only) into storage/datasets/work/rwf2000."""
import sys
from pathlib import Path

import py7zr

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'storage/datasets/raw/farazv2__violence-detection-rwf2000'
DEST = ROOT / 'storage/datasets/work/rwf2000'
VIDEO = ('.avi', '.mp4', '.mov', '.mkv')

archive = next(RAW.glob('RWF-2000_full.7z'), None)
if archive is None:
    sys.exit('archive not downloaded yet')
DEST.mkdir(parents=True, exist_ok=True)
with py7zr.SevenZipFile(archive) as z:
    names = [n for n in z.getnames() if n.lower().endswith(VIDEO)]
    for n in names:
        if not (DEST / n).resolve().is_relative_to(DEST.resolve()):
            sys.exit(f'unsafe path in archive: {n}')
    print(len(names), 'videos in archive', flush=True)
    z.extract(path=DEST, targets=names)
print('done', flush=True)
