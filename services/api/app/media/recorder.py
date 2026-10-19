"""Segmented MP4 recorder, snapshot writer, and clip exporter."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid
import cv2
import numpy as np

from .. import database as db
from .. import settings

SEGMENT_DURATION_S = 10.0


def _decode_jpeg(jpeg_bytes: bytes) -> np.ndarray | None:
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    if arr.size == 0:
        return None
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _jpeg_dimensions(jpeg_bytes: bytes) -> tuple[int, int]:
    img = _decode_jpeg(jpeg_bytes)
    if img is None:
        return (640, 360)
    h, w = img.shape[:2]
    return (int(w), int(h))


def _write_mp4_from_frames(frames: list[tuple[float, bytes]], out_path: Path, target_w: int = 0, target_h: int = 0) -> tuple[int, int, float]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    decoded: list[tuple[float, np.ndarray]] = []
    for ts, jb in frames:
        img = _decode_jpeg(jb)
        if img is not None:
            decoded.append((ts, img))
    if not decoded:
        return (0, 0, 0.0)
    first_img = decoded[0][1]
    h, w = first_img.shape[:2]
    if target_w > 0 and target_h > 0:
        w, h = target_w, target_h
    # Ensure even dimensions for H.264/MP4 compatibility
    w = max(2, w - (w % 2))
    h = max(2, h - (h % 2))

    duration = max(0.2, decoded[-1][0] - decoded[0][0]) if len(decoded) > 1 else 1.0
    fps = max(2.0, min(24.0, len(decoded) / duration)) if len(decoded) > 1 else 5.0

    tmp_raw = out_path.with_suffix(".raw.mp4")
    writer = None
    for fourcc_name in ("avc1", "H264", "mp4v"):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
        candidate = cv2.VideoWriter(str(tmp_raw), fourcc, fps, (w, h))
        if candidate.isOpened():
            writer = candidate
            break
    if writer is None:
        return (w, h, fps)

    for _, img in decoded:
        if img.shape[1] != w or img.shape[0] != h:
            img = cv2.resize(img, (w, h))
        writer.write(img)
    writer.release()

    # If ffmpeg is available, remux with +faststart / fragmented MP4 for instant browser Range playback
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin and tmp_raw.exists() and tmp_raw.stat().st_size > 0:
        try:
            proc = subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(tmp_raw),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart+frag_keyframe+empty_moov",
                    str(out_path),
                ],
                capture_output=True,
                timeout=12.0,
            )
            if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                tmp_raw.unlink(missing_ok=True)
                return (w, h, round(fps, 2))
        except Exception:
            pass

    if tmp_raw.exists():
        tmp_raw.replace(out_path)
    return (w, h, round(fps, 2))


class CameraSegmentRecorder:
    """Buffers live JPEG frames per camera and flushes 10-second MP4 segments."""

    def __init__(self, camera_id: str, segment_seconds: float = SEGMENT_DURATION_S):
        self.camera_id = camera_id
        self.segment_seconds = segment_seconds
        self._lock = threading.Lock()
        self._frames: list[tuple[float, bytes]] = []
        self._start_ts: float | None = None
        self._last_ts: float | None = None
        self._width: int = 0
        self._height: int = 0

    def append_frame(self, jpeg_bytes: bytes, ts: float | None = None, width: int = 0, height: int = 0) -> dict | None:
        now_ts = float(ts if ts is not None else time.time())
        to_flush: list[tuple[float, bytes]] | None = None
        start_ts = now_ts
        end_ts = now_ts
        w, h = width, height

        with self._lock:
            if self._start_ts is None:
                self._start_ts = now_ts
            self._last_ts = now_ts
            if width > 0 and height > 0:
                self._width, self._height = width, height
            self._frames.append((now_ts, jpeg_bytes))
            if (now_ts - self._start_ts) >= self.segment_seconds and len(self._frames) >= 2:
                to_flush = list(self._frames)
                start_ts = self._start_ts
                end_ts = now_ts
                w, h = self._width, self._height
                self._frames = []
                self._start_ts = None

        if to_flush:
            return self._write_segment(to_flush, start_ts, end_ts, w, h)
        return None

    def flush(self) -> dict | None:
        with self._lock:
            if not self._frames or self._start_ts is None:
                return None
            to_flush = list(self._frames)
            start_ts = self._start_ts
            end_ts = max(self._last_ts or start_ts + 0.5, start_ts + 0.5)
            w, h = self._width, self._height
            self._frames = []
            self._start_ts = None
        return self._write_segment(to_flush, start_ts, end_ts, w, h)

    def _write_segment(self, frames: list[tuple[float, bytes]], start_ts: float, end_ts: float, width: int, height: int) -> dict | None:
        base = settings.active_storage()
        day_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        start_ms = int(start_ts * 1000)
        end_ms = int(max(end_ts, start_ts + 0.25) * 1000)
        seg_id = f"seg_{self.camera_id}_{start_ms}_{end_ms}"
        rel_path = Path("recordings") / self.camera_id / day_str / f"{seg_id}.mp4"
        abs_path = base / rel_path

        w, h, fps = _write_mp4_from_frames(frames, abs_path, width, height)
        if not abs_path.exists() or abs_path.stat().st_size == 0:
            return None

        # Count any events on this camera during [start_ts, end_ts]
        event_count = 0
        try:
            for ev in db.all_objects("event"):
                if ev.get("camera", {}).get("id") == self.camera_id:
                    ev_ts = _iso_to_epoch(ev.get("first_seen_at") or ev.get("created_at"))
                    if ev_ts and (start_ts - 2.0) <= ev_ts <= (end_ts + 2.0):
                        event_count += 1
        except Exception:
            pass

        seg_record = {
            "segment_id": seg_id,
            "camera_id": self.camera_id,
            "start_ts": round(start_ts, 3),
            "end_ts": round(max(end_ts, start_ts + 0.25), 3),
            "duration_s": round(max(0.25, end_ts - start_ts), 3),
            "path": str(rel_path).replace("\\", "/"),
            "size_bytes": int(abs_path.stat().st_size),
            "width": w or width or 640,
            "height": h or height or 360,
            "fps": fps or 5.0,
            "codec": "h264",
            "has_events": 1 if event_count > 0 else 0,
            "event_count": event_count,
            "created_at": time.time(),
        }
        db.insert_recording_segment(seg_record)
        return seg_record


def _iso_to_epoch(val: str | float | None) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class RecorderManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._recorders: dict[str, CameraSegmentRecorder] = {}

    def get(self, camera_id: str) -> CameraSegmentRecorder:
        with self._lock:
            rec = self._recorders.get(camera_id)
            if rec is None:
                rec = CameraSegmentRecorder(camera_id)
                self._recorders[camera_id] = rec
            return rec

    def append_frame(self, camera_id: str, jpeg_bytes: bytes, ts: float | None = None, width: int = 0, height: int = 0) -> dict | None:
        return self.get(camera_id).append_frame(jpeg_bytes, ts=ts, width=width, height=height)

    def flush(self, camera_id: str) -> dict | None:
        with self._lock:
            rec = self._recorders.get(camera_id)
        return rec.flush() if rec else None

    def flush_all(self) -> list[dict]:
        with self._lock:
            recorders = list(self._recorders.values())
        out = []
        for r in recorders:
            seg = r.flush()
            if seg:
                out.append(seg)
        return out


RECORDER_MANAGER = RecorderManager()


def save_snapshot_bytes(
    camera_id: str,
    jpeg_bytes: bytes,
    kind: str = "stream",
    source_event_id: str | None = None,
    ts: float | None = None,
) -> dict:
    now_ts = float(ts if ts is not None else time.time())
    snap_id = f"snap_{uuid.uuid4().hex[:12]}"
    base = settings.active_storage()
    rel_path = Path("snapshots") / camera_id / f"{snap_id}.jpg"
    abs_path = base / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(jpeg_bytes)
    w, h = _jpeg_dimensions(jpeg_bytes)
    record = {
        "snapshot_id": snap_id,
        "camera_id": camera_id,
        "ts": round(now_ts, 3),
        "kind": kind,
        "path": str(rel_path).replace("\\", "/"),
        "width": w,
        "height": h,
        "size_bytes": len(jpeg_bytes),
        "source_event_id": source_event_id,
    }
    db.insert_snapshot(record)
    db.insert_moment(
        {
            "moment_id": f"mom_{snap_id}",
            "camera_id": camera_id,
            "ts": round(now_ts, 3),
            "kind": "screenshot",
            "label": f"{kind.title()} Snapshot",
            "summary": f"Captured {w}x{h} {kind} snapshot on camera {camera_id}.",
            "media_url": f"/api/v1/snapshots/{snap_id}.jpg",
            "snapshot_id": snap_id,
            "event_id": source_event_id,
        }
    )
    return {
        **record,
        "url": f"/api/v1/snapshots/{snap_id}.jpg",
    }


def export_camera_clip(camera_id: str, from_ts: float, to_ts: float, recent_frames: list[tuple[float, bytes]] | None = None) -> dict:
    # Flush any buffered frames for this camera so recent activity is on disk
    RECORDER_MANAGER.flush(camera_id)
    base = settings.active_storage()
    segments = db.list_recording_segments(camera_id=camera_id, from_ts=from_ts, to_ts=to_ts, limit=100)
    export_id = f"exp_{uuid.uuid4().hex[:12]}"
    rel_path = Path("exports") / f"{export_id}.mp4"
    abs_path = base / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    collected_frames: list[tuple[float, bytes]] = []
    for seg in segments:
        seg_file = base / seg["path"]
        if not seg_file.exists():
            continue
        cap = cv2.VideoCapture(str(seg_file))
        fps = cap.get(cv2.CAP_PROP_FPS) or seg.get("fps") or 5.0
        idx = 0
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame_ts = float(seg["start_ts"]) + (idx / max(1.0, fps))
            idx += 1
            if from_ts <= frame_ts <= to_ts or len(segments) == 1:
                ok_enc, enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok_enc:
                    collected_frames.append((frame_ts, enc.tobytes()))
        cap.release()

    if not collected_frames and recent_frames:
        for f_ts, f_bytes in recent_frames:
            if from_ts <= f_ts <= to_ts:
                collected_frames.append((f_ts, f_bytes))
        if not collected_frames:
            collected_frames = list(recent_frames[-30:])

    if not collected_frames and segments:
        # Copy first matching segment directly if frame extraction yielded empty
        first_seg_path = base / segments[0]["path"]
        if first_seg_path.exists():
            shutil.copy2(first_seg_path, abs_path)

    if collected_frames:
        _write_mp4_from_frames(collected_frames, abs_path)

    if not abs_path.exists() or abs_path.stat().st_size == 0:
        # Generate a minimal valid black frame MP4 if no frames were recorded yet in that range
        blank = np.zeros((360, 640, 3), dtype=np.uint8)
        ok_enc, enc = cv2.imencode(".jpg", blank)
        if ok_enc:
            _write_mp4_from_frames([(from_ts, enc.tobytes()), (to_ts, enc.tobytes())], abs_path, 640, 360)

    size_bytes = int(abs_path.stat().st_size) if abs_path.exists() else 0
    duration_s = round(max(0.5, to_ts - from_ts), 2)
    record = {
        "export_id": export_id,
        "camera_id": camera_id,
        "start_ts": round(from_ts, 3),
        "end_ts": round(to_ts, 3),
        "duration_s": duration_s,
        "path": str(rel_path).replace("\\", "/"),
        "size_bytes": size_bytes,
        "created_at": time.time(),
    }
    db.insert_export(record)
    return {
        **record,
        "url": f"/api/v1/exports/{export_id}.mp4",
    }
