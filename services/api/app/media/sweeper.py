"""Storage retention sweeper and disk usage summary."""
from __future__ import annotations

from pathlib import Path
import shutil
import time
import yaml

from .. import database as db
from .. import settings


def load_retention_policy() -> dict:
    cfg_path = settings.ROOT / "config" / "media.yaml"
    defaults = {
        "recordings_days": 7,
        "snapshots_days": 30,
        "exports_days": 30,
        "min_free_gb": 20,
        "sweep_interval_seconds": 900,
    }
    if cfg_path.exists():
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if isinstance(data.get("retention"), dict):
                defaults.update(data["retention"])
        except Exception:
            pass
    return defaults


def _folder_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)
    total = 0
    count = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
                count += 1
            except OSError:
                pass
    return (total, count)


def get_storage_summary() -> dict:
    base = settings.active_storage()
    usage = shutil.disk_usage(base)
    rec_bytes, rec_count = _folder_size(base / "recordings")
    snap_bytes, snap_count = _folder_size(base / "snapshots")
    exp_bytes, exp_count = _folder_size(base / "exports")
    return {
        "total_bytes": int(usage.total),
        "free_bytes": int(usage.free),
        "used_bytes": int(usage.used),
        "recordings_bytes": int(rec_bytes),
        "snapshots_bytes": int(snap_bytes),
        "exports_bytes": int(exp_bytes),
        "recordings_count": int(rec_count),
        "snapshots_count": int(snap_count),
        "exports_count": int(exp_count),
        "retention_policy": load_retention_policy(),
    }


def run_retention_sweep(override_policy: dict | None = None) -> dict:
    policy = load_retention_policy()
    if override_policy:
        policy.update(override_policy)
    base = settings.active_storage()
    now_ts = time.time()
    rec_cutoff = now_ts - float(policy.get("recordings_days", 7)) * 86400.0
    snap_cutoff = now_ts - float(policy.get("snapshots_days", 30)) * 86400.0

    deleted_segments = 0
    deleted_snapshots = 0

    for seg in db.list_recording_segments(limit=2000):
        if float(seg["end_ts"]) < rec_cutoff:
            p = base / seg["path"]
            p.unlink(missing_ok=True)
            db.delete_recording_segment(seg["segment_id"])
            deleted_segments += 1

    for snap in db.list_snapshots(limit=2000):
        if float(snap["ts"]) < snap_cutoff:
            p = base / snap["path"]
            p.unlink(missing_ok=True)
            db.delete_snapshot(snap["snapshot_id"])
            deleted_snapshots += 1

    # Also enforce min_free_gb by pruning oldest segments if disk is below threshold
    min_free_bytes = int(float(policy.get("min_free_gb", 20)) * (1024 ** 3))
    if override_policy and "max_recordings_bytes" in override_policy:
        max_rec_bytes = int(override_policy["max_recordings_bytes"])
        segs = db.list_recording_segments(limit=2000)
        total_rec = sum(int(s.get("size_bytes", 0)) for s in segs)
        for seg in segs:
            if total_rec <= max_rec_bytes:
                break
            p = base / seg["path"]
            p.unlink(missing_ok=True)
            db.delete_recording_segment(seg["segment_id"])
            total_rec -= int(seg.get("size_bytes", 0))
            deleted_segments += 1
    else:
        usage = shutil.disk_usage(base)
        if usage.free < min_free_bytes:
            for seg in db.list_recording_segments(limit=200):
                p = base / seg["path"]
                p.unlink(missing_ok=True)
                db.delete_recording_segment(seg["segment_id"])
                deleted_segments += 1
                if shutil.disk_usage(base).free >= min_free_bytes:
                    break

    return {
        "deleted_segments": deleted_segments,
        "deleted_snapshots": deleted_snapshots,
        "summary": get_storage_summary(),
    }
