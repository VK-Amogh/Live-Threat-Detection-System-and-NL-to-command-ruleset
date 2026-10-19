"""Detect that the camera view has moved, so drawn zones, lines and anchors can no longer be trusted.

The reference is the first sharp frame seen after geometry is configured. Later frames are matched to it with ORB features
and a similarity transform; the largest corner displacement (as a share of frame width) is the shift. Two consecutive
moved frames suspend geometry rules, three consecutive stable frames resume them, so one bump or one blurred frame does
not flap the state."""

from dataclasses import dataclass

import cv2
import numpy as np

SMALL_WIDTH = 320
MOVE_FRAMES_TO_SUSPEND = 2
STABLE_FRAMES_TO_RESUME = 3


@dataclass(frozen=True)
class GuardStatus:
    suspended: bool
    reason: str | None = None
    shift_rel: float | None = None


def sharpness(frame) -> float:
    """Variance of the Laplacian of the 320 px grey image: near zero for black or heavily smeared frames."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    height, width = gray.shape[:2]
    small = cv2.resize(gray, (SMALL_WIDTH, max(1, round(height * SMALL_WIDTH / width))))
    return float(cv2.Laplacian(small, cv2.CV_64F).var())


class SceneGuard:
    def __init__(self, max_shift_rel: float = 0.04, min_matches: int = 12):
        self.max_shift_rel = max_shift_rel
        self.min_matches = min_matches
        self.orb = cv2.ORB_create(500)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.reset(None)

    def reset(self, geometry_size: tuple[int, int] | None):
        self.geometry_size = geometry_size
        self.reference = None
        self.moved_streak = self.stable_streak = 0
        self.suspended = False
        self.reason: str | None = None

    def _features(self, frame):
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (SMALL_WIDTH, max(1, round(height * SMALL_WIDTH / width))))
        keypoints, descriptors = self.orb.detectAndCompute(small, None)
        return keypoints, descriptors, small.shape

    def _measure(self, frame) -> tuple[bool, str | None, float | None]:
        height, width = frame.shape[:2]
        if self.geometry_size and (width > height) != (self.geometry_size[0] > self.geometry_size[1]):
            return True, "orientation differs from the geometry snapshot", None
        keypoints, descriptors, shape = self._features(frame)
        if self.reference is None:
            self.reference = (keypoints, descriptors, shape)
            return False, None, 0.0
        ref_points, ref_descriptors, ref_shape = self.reference
        if descriptors is None or ref_descriptors is None or len(keypoints) < self.min_matches:
            return True, "scene not recognisable", None
        matches = sorted(self.matcher.match(ref_descriptors, descriptors), key=lambda m: m.distance)[:150]
        if len(matches) < self.min_matches:
            return True, "scene not recognisable", None
        source = np.float32([ref_points[m.queryIdx].pt for m in matches])
        target = np.float32([keypoints[m.trainIdx].pt for m in matches])
        transform, _ = cv2.estimateAffinePartial2D(source, target, ransacReprojThreshold=3.0)
        if transform is None:
            return True, "no consistent motion between frames", None
        corners = np.float32([[0, 0], [ref_shape[1], 0], [ref_shape[1], ref_shape[0]], [0, ref_shape[0]]])
        moved = corners @ transform[:, :2].T + transform[:, 2]
        shift = float(np.max(np.linalg.norm(moved - corners, axis=1))) / ref_shape[1]
        return shift > self.max_shift_rel, f"view shifted {shift:.1%}" if shift > self.max_shift_rel else None, shift

    def update(self, frame) -> GuardStatus:
        moved, reason, shift = self._measure(frame)
        if moved:
            self.moved_streak, self.stable_streak = self.moved_streak + 1, 0
        else:
            self.stable_streak, self.moved_streak = self.stable_streak + 1, 0
        if self.moved_streak >= MOVE_FRAMES_TO_SUSPEND:
            self.suspended, self.reason = True, reason
        elif self.suspended and self.stable_streak >= STABLE_FRAMES_TO_RESUME:
            self.suspended, self.reason = False, None
        return GuardStatus(self.suspended, self.reason, shift)
