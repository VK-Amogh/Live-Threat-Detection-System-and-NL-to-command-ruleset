"""Bounded JPEG pre-roll and delayed local evidence clips."""

from collections import deque
from pathlib import Path
import subprocess

import cv2
import imageio_ffmpeg
import numpy as np


class EvidenceBuffer:
    def __init__(self, media_root: Path, fps: float, pre_roll_s: float, post_roll_s: float):
        self.media_root = media_root
        self.fps = fps
        self.pre_roll_s = pre_roll_s
        self.post_roll_s = post_roll_s
        self.frames: deque[tuple[float, bytes]] = deque()
        self.pending: dict[str, tuple[float, list[bytes]]] = {}

    def append(self, ts: float, jpeg: bytes) -> list[str]:
        self.frames.append((ts, jpeg))
        while self.frames and ts - self.frames[0][0] > self.pre_roll_s:
            self.frames.popleft()
        completed = []
        for event_id, (deadline, pieces) in list(self.pending.items()):
            pieces.append(jpeg)
            if ts >= deadline - 1e-6:
                self._write_clip(event_id, pieces)
                self.pending.pop(event_id, None)
                completed.append(event_id)
        return completed

    def start(self, event_id: str, ts: float, jpeg: bytes):
        folder = self.media_root / event_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "frame.jpg").write_bytes(jpeg)
        if event_id not in self.pending:
            self.pending[event_id] = (ts + self.post_roll_s, [piece for _, piece in self.frames])

    def _write_clip(self, event_id: str, pieces: list[bytes]):
        folder = self.media_root / event_id
        folder.mkdir(parents=True, exist_ok=True)
        first = cv2.imdecode(np.frombuffer(pieces[0], dtype="uint8"), cv2.IMREAD_COLOR)
        if first is None:
            raise ValueError("Evidence frame cannot be decoded")
        height, width = first.shape[:2]
        raw = folder / "clip.avi"
        writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"MJPG"), self.fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError("Evidence clip writer unavailable")
        try:
            for piece in pieces:
                frame = cv2.imdecode(np.frombuffer(piece, dtype="uint8"), cv2.IMREAD_COLOR)
                if frame is not None:
                    writer.write(cv2.resize(frame, (width, height)))
        finally:
            writer.release()
        target = folder / "clip.mp4"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(raw),
                   "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)]
        result = subprocess.run(command, capture_output=True, timeout=120,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        raw.unlink(missing_ok=True)
        if result.returncode:
            raise RuntimeError("Evidence clip transcode failed")
