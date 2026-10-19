"""Pick three spaced, context-preserving frames from a completed clip."""

import json
from pathlib import Path

import cv2
import numpy as np


def _crop_and_encode(frame, bbox) -> bytes | None:
    if bbox is not None:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        margin = max(60, round(max(x2 - x1, y2 - y1) * 1.5))
        left, top = max(0, x1 - margin), max(0, y1 - margin)
        right, bottom = min(width, x2 + margin), min(height, y2 + margin)
        if right > left and bottom > top:
            frame = frame[round(top):round(bottom), round(left):round(right)]
    if frame.shape[1] > 640:
        scale = 640 / frame.shape[1]
        frame = cv2.resize(frame, (640, max(1, round(frame.shape[0] * scale))))
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return jpeg.tobytes() if ok else None


def pack_frames(folder: Path) -> list[bytes]:
    """Three spaced frames from the fire-time evidence pack, each cropped around the subject as it was in that frame.

    The clip only exists after the post-roll, and cropping every clip frame with the trigger-frame box showed empty floor
    whenever the person had moved."""
    index = json.loads((folder / "pack.json").read_text(encoding="utf-8"))["frames"]
    picks = sorted({0, (len(index) - 1) // 2, len(index) - 1}) if index else []
    output = []
    for position in picks:
        item = index[position]
        frame = cv2.imdecode(np.frombuffer((folder / item["file"]).read_bytes(), dtype="uint8"), cv2.IMREAD_COLOR)
        if frame is not None:
            jpeg = _crop_and_encode(frame, item.get("bbox"))
            if jpeg:
                output.append(jpeg)
    return output


def selected_frames(clip: Path, bbox: tuple[int, int, int, int] | None = None, pack: Path | None = None) -> list[bytes]:
    if pack is not None and (pack / "pack.json").is_file():
        frames = pack_frames(pack)
        if frames:
            return frames
    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise ValueError("Visual-review clip cannot be opened")
    try:
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if count < 1:
            raise ValueError("Visual-review clip has no frames")
        positions = sorted({0, round((count - 1) / 2), count - 1})
        output = []
        for index in positions:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                continue
            if bbox is not None:
                height, width = frame.shape[:2]
                x1, y1, x2, y2 = bbox
                margin = max(60, round(max(x2 - x1, y2 - y1) * 1.5))
                left, top = max(0, x1 - margin), max(0, y1 - margin)
                right, bottom = min(width, x2 + margin), min(height, y2 + margin)
                if right > left and bottom > top:
                    frame = frame[top:bottom, left:right]
            if frame.shape[1] > 640:
                scale = 640 / frame.shape[1]
                frame = cv2.resize(frame, (640, max(1, round(frame.shape[0] * scale))))
            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                output.append(jpeg.tobytes())
        if len(output) < 3:
            raise ValueError("Visual-review clip has fewer than three readable frames")
        return output
    finally:
        capture.release()
