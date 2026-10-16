"""Pick three spaced, context-preserving frames from a completed clip."""

from pathlib import Path

import cv2


def selected_frames(clip: Path, bbox: tuple[int, int, int, int] | None = None) -> list[bytes]:
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
