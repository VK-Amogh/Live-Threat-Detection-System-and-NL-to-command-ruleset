"""Reconnect a live video source and emit its most recent frames."""

import time

import cv2


def frames(source: str, stop, reconnect_max_s: float = 30):
    delay = 1.0
    frame_id = 0
    while not stop():
        capture = cv2.VideoCapture(int(source) if source.isdigit() else source)
        if capture.isOpened():
            delay = 1.0
            try:
                while not stop():
                    ok, frame = capture.read()
                    if not ok:
                        break
                    frame_id += 1
                    yield frame_id, time.time(), frame
            finally:
                capture.release()
        else:
            capture.release()
        if stop():
            break
        deadline = time.monotonic() + delay
        while not stop() and time.monotonic() < deadline:
            yield frame_id, time.time(), None
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        delay = min(reconnect_max_s, delay * 2)
