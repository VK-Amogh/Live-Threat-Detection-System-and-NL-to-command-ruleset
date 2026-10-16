"""Contact sheet of 'threat-free' CCTV test frames on which the deployed stack alerts for a weapon (label-noise audit)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'contracts/src')]
import server  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

server.load_models()
root = ROOT / 'storage/datasets/weapons'
clean = [p for p in sorted((root / 'images/test').glob('cctv_*.jpg')) if not (root / 'labels/test' / (p.stem + '.txt')).read_text().strip()]
print(len(clean), 'clean CCTV test frames')
hits = []
for p in clean:
    detections = [d for d in server.decide(server.analyse(Image.open(p).convert('RGB'), None)) if d.category == 'WEAPON_DETECTED']
    if detections:
        hits.append((p, detections))
print(len(hits), 'alerted')
tiles = []
for p, detections in hits[:18]:
    im = Image.open(p).convert('RGB')
    d = ImageDraw.Draw(im)
    for x in detections:
        d.rectangle(x.box, outline='red', width=4)
        d.text((x.box[0], max(0, x.box[1] - 14)), f'{x.class_name} p={x.confidence:.3f} yolo={x.detector_confidence:.2f}', fill='yellow')
    tiles.append(im.resize((426, 240)))
sheet = Image.new('RGB', (426 * 3, 240 * ((len(tiles) + 2) // 3)))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 3) * 426, (i // 3) * 240))
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'storage/eval/cctv_clean_alerts.jpg'
sheet.save(out)
print('saved', out)
