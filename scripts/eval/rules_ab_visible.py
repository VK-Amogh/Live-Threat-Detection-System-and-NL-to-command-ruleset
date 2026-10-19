"""Usage: python scripts/eval/rules_ab_visible.py <out dir>   (env MIN_SCORE=0.65 and SKIP_OLD=1 are optional)

A/B on the stored phone recordings: old pipeline (conf 0.35, no gates) vs new (tracker conf 0.1 + plausibility gates + guards).

Rule: "a person is visible" (the rule that produced the false alerts). Each segment is replayed independently at ~5 fps.
Saves every alert's trigger frame (box drawn) so the alerts can be labelled by eye."""
import copy
import time
import glob
import json
import sys
import tempfile
from pathlib import Path

import cv2
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from td_contracts import RuleSpec
from services.rules.evidence import EvidenceBuffer
from services.rules.runtime import RuleRuntime, build_detector

TIMES = {}
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
base = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
old = copy.deepcopy(base)
old["quality"] = {}
old["scene_guard"] = {"enabled": False}
del old["detector"]["tracker_conf"]
new = copy.deepcopy(base)
import os
if os.environ.get("REQUIRE_POSE"):
    new["quality"]["person"]["require_pose_support"] = True
if os.environ.get("MIN_SCORE"):
    new["quality"]["person"]["min_track_score"] = float(os.environ["MIN_SCORE"])
RULE = RuleSpec.model_validate({"rule_id": "r_visible", "camera_id": "cam", "version": 1, "name": "person visible", "entity": "person",
                                "when": {"type": "entity_present"}, "min_hold_s": 1.5, "cooldown_s": 5, "support_level": "SUPPORTED", "status": "active",
                                "episode": {"cooldown_scope": "actor"}})


class NoClips(EvidenceBuffer):
    def _write_clip(self, event_id, pieces):
        return None


def run(config, label):
    results = []
    detector_cache = {}
    for path in sorted(glob.glob(str(ROOT / "storage/recordings/*/*/*.mp4"))):
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
        stride = max(1, round(fps / 5))
        detector = build_detector("cam", config)       # fresh tracker state per segment
        with tempfile.TemporaryDirectory() as scratch:
            evidence = NoClips(Path(scratch), 5, 2, 0.0)
            runtime = RuleRuntime("cam", config, evidence, "AB")
            runtime.configure([RULE], None)
            index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                index += 1
                if (index - 1) % stride:
                    continue
                ts = 1_760_000_000.0 + (index - 1) / fps
                jpeg = cv2.imencode(".jpg", frame)[1].tobytes()
                evidence.append(ts, jpeg)
                obs = detector.observe(frame, index, ts)
                begin = time.perf_counter()
                emitted = runtime.process(frame, obs, ts, jpeg)
                TIMES.setdefault(label, []).append((time.perf_counter() - begin) * 1000)
                for event in emitted:
                    box = event.evidence_bbox
                    shown = frame.copy()
                    if box:
                        cv2.rectangle(shown, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 6)
                    name = f"{label}_{Path(path).stem[-13:]}_{(index - 1) / fps:.1f}.jpg"
                    cv2.imwrite(str(OUT / name), shown)
                    results.append({"segment": Path(path).name, "t_s": round((index - 1) / fps, 2), "bbox": box, "file": name,
                                    "score": [c for c in event.verification.checks if "score" in c]})
        cap.release()
    return results


a, b = ([] if os.environ.get("SKIP_OLD") else run(old, "old")), run(new, "new")
(OUT / "ab.json").write_text(json.dumps({"old": a, "new": b}, indent=1))
print("old alerts:", len(a), " new alerts:", len(b))
for name, values in TIMES.items():
    values.sort()
    print(f"runtime.process per processed frame [{name}]: n={len(values)} p50={values[len(values) // 2]:.1f} ms p95={values[int(0.95 * (len(values) - 1))]:.1f} ms")
for item in a:
    print("OLD", item["file"], item["bbox"])
for item in b:
    print("NEW", item["file"], item["bbox"], item["score"])
