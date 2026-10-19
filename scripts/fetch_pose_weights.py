"""Install the person-pose weights once, so touch/sit rules can use skeletons. Never run at runtime.

  python scripts/fetch_pose_weights.py

Downloads `yolo26n-pose.pt` (Ultralytics release asset, a few MB; AGPL-3.0 like the other Ultralytics weights) to
weights/yolo26n-pose.pt. Ultralytics does not publish a checksum for it, so the SHA-256 is recorded on the first fetch in
weights/yolo26n-pose.pt.sha256 (trust on first use) and every later run refuses a file that no longer matches it.
`quality.person.require_pose_support` is on in config/rules.yaml: with the weights present, every "person" must also show a
coherent skeleton (this is what removes backpack and fabric close-ups that the detector scores confidently).
"""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "weights/yolo26n-pose.pt"
RECORD = TARGET.with_suffix(".pt.sha256")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if not TARGET.is_file():
        from ultralytics.utils.downloads import attempt_download_asset
        attempt_download_asset(str(TARGET))
    if not TARGET.is_file():
        print("download failed: weights/yolo26n-pose.pt is missing", file=sys.stderr)
        return 1
    digest = sha256(TARGET)
    if RECORD.is_file():
        if RECORD.read_text(encoding="utf-8").split()[0] != digest:
            print("checksum differs from the one recorded on first fetch; delete both files only if you trust the new weights", file=sys.stderr)
            return 2
        print(f"verified {TARGET.name} ({TARGET.stat().st_size / 1e6:.1f} MB), sha256 {digest[:16]}…")
    else:
        RECORD.write_text(f"{digest}  {TARGET.name}\n", encoding="utf-8")
        print(f"installed {TARGET.name} ({TARGET.stat().st_size / 1e6:.1f} MB); recorded sha256 {digest[:16]}… (first use)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
