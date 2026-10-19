"""How much the picture inside a drawn zone has changed: the signal behind "the door opens".

A door swinging open changes the pixels of the door area. Each watched zone keeps a slowly adapting baseline of its
(blurred, shrunken, masked) grey crop; the reported change is the share of the zone's pixels that now differ from it by more
than a fixed amount, after removing the brightness shift of the WHOLE frame (auto-exposure moves everything together; the
zone's own median cannot be used, because an opening door replaces most of the zone). Slow drift is absorbed into the baseline,
and a lasting change (a door left open) becomes the new normal after a few seconds so the next opening is seen again.

People are masked out: pixels covered by a person's box (slightly enlarged) are neither compared nor learned, so someone walking
or standing in front of the door is not "the door opening" and does not contaminate the baseline. If a person hides most of the
zone the change is reported as UNKNOWN (-1: nothing can be judged) and the baseline is left alone. The exposure shift is
measured on background pixels only, because a person in a dark jacket entering the frame makes the phone raise its exposure."""

import cv2
import numpy as np

SIZE = 48              # the zone crop is shrunk to SIZE x SIZE before comparing
PIXEL_DELTA = 28       # grey levels a pixel must differ from the baseline to count as changed
ADAPT_BELOW = 0.12     # below this changed share the baseline follows the scene (lighting drift)
ABSORB_AFTER_S = 8.0   # a change that lasts this long is the new normal
MIN_VISIBLE = 0.25     # share of the zone that must be free of people for a judgement
PERSON_MARGIN = 0.08   # people's boxes are enlarged by this share before masking


class ZoneWatcher:
    def __init__(self):
        self.base: dict[str, np.ndarray] = {}
        self.high_since: dict[str, float] = {}
        self.frame_mean: float | None = None

    def reset(self):
        self.base.clear()
        self.high_since.clear()
        self.frame_mean = None

    @staticmethod
    def _crop(gray, polygon):
        points = np.array([[round(x), round(y)] for x, y in polygon], dtype=np.int32)
        x, y, w, h = cv2.boundingRect(points)
        height, width = gray.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(w, width - x), min(h, height - y)
        if w < 4 or h < 4:
            return None, None, None
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [points - np.array([x, y], dtype=np.int32)], 255)
        crop = cv2.resize(cv2.GaussianBlur(gray[y:y + h, x:x + w], (5, 5), 0), (SIZE, SIZE), interpolation=cv2.INTER_AREA)
        return crop.astype(np.float32), cv2.resize(mask, (SIZE, SIZE), interpolation=cv2.INTER_NEAREST) > 0, (x, y, w, h)

    @staticmethod
    def _people(shape, origin, boxes) -> np.ndarray:
        x, y, w, h = origin
        blocked = np.zeros((SIZE, SIZE), dtype=bool)
        for x1, y1, x2, y2 in boxes:
            margin_x, margin_y = (x2 - x1) * PERSON_MARGIN, (y2 - y1) * PERSON_MARGIN
            left, right = int((x1 - margin_x - x) / w * SIZE), int(np.ceil((x2 + margin_x - x) / w * SIZE))
            top, bottom = int((y1 - margin_y - y) / h * SIZE), int(np.ceil((y2 + margin_y - y) / h * SIZE))
            blocked[max(0, top):max(0, bottom), max(0, left):max(0, right)] = True
        return blocked

    @staticmethod
    def _background_mean(gray, boxes) -> float:
        """Mean brightness of the picture outside people (auto-exposure shows in the background, not on a person)."""
        small = cv2.resize(gray, (gray.shape[1] // 8 or 1, gray.shape[0] // 8 or 1), interpolation=cv2.INTER_AREA)
        keep = np.ones(small.shape, dtype=bool)
        for x1, y1, x2, y2 in boxes:
            keep[max(0, int(y1 // 8)):int(np.ceil(y2 / 8)), max(0, int(x1 // 8)):int(np.ceil(x2 / 8))] = False
        return float(small[keep].mean()) if keep.mean() >= 0.3 else float(small.mean())

    def measure(self, frame, zones: dict, names, ts: float, exclude=()) -> dict[str, float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        mean = self._background_mean(gray, exclude)
        if self.frame_mean is None:
            self.frame_mean = mean
        shift = max(-60.0, min(60.0, mean - self.frame_mean))     # exposure change of the whole picture
        result = {}
        for name in names:
            if name not in zones:
                continue
            current, mask, origin = self._crop(gray, zones[name])
            if current is None or not mask.any():
                continue
            valid = mask & ~self._people(gray.shape, origin, exclude) if len(exclude) else mask
            base = self.base.get(name)
            if base is None:
                self.base[name] = current
                result[name] = 0.0
                continue
            if valid.sum() < MIN_VISIBLE * mask.sum():
                result[name] = -1.0                                 # a person hides the zone: nothing to judge, nothing learned
                continue
            difference = current - base - shift
            change = float((np.abs(difference[valid]) > PIXEL_DELTA).mean())
            if change < ADAPT_BELOW:
                updated = base.copy()
                updated[valid] = 0.9 * base[valid] + 0.1 * current[valid]
                self.base[name] = updated
                self.high_since.pop(name, None)
            else:
                started = self.high_since.setdefault(name, ts)
                if ts - started >= ABSORB_AFTER_S:
                    absorbed = base.copy()
                    absorbed[valid] = current[valid]
                    self.base[name] = absorbed
                    self.high_since.pop(name, None)
            result[name] = change
        if all(0 <= value < ADAPT_BELOW for value in result.values()):
            self.frame_mean = 0.9 * self.frame_mean + 0.1 * mean
        return result
