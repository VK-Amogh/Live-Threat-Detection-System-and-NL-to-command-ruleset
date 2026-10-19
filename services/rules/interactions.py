"""Person-object relations from boxes and COCO keypoints. Pure functions; no frame pixels, no engine state.

Box overlap alone never establishes contact or sitting: touching needs a hand keypoint inside the object's region, and
sitting needs both hips inside the seat band of the nearest candidate seat with an upright torso and bent legs.
Missing keypoints mean "cannot tell", which callers treat as not matched."""

from math import hypot

from td_contracts import ObservedTrack
from .geometry import box_center, box_expand, box_gap, point_in_box

MIN_KP_CONF = 0.4
NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP, L_KNEE, R_KNEE = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14


def keypoint(track: ObservedTrack, index: int):
    if not track.keypoints or index >= len(track.keypoints):
        return None
    x, y, conf = track.keypoints[index]
    return (x, y) if conf >= MIN_KP_CONF else None


def box_height(track: ObservedTrack) -> float:
    return max(1.0, track.bbox[3] - track.bbox[1])


def near(track: ObservedTrack, box, gap_rel: float = 0.15, depth_rel: float = 0.3) -> bool:
    """Person box within `gap_rel` x person height of the object box, standing at about the same depth
    (the bottom of the person is near the bottom of the object)."""
    height = box_height(track)
    return box_gap(track.bbox, box) <= gap_rel * height and abs(track.foot[1] - box[3]) <= depth_rel * height


def hand_points(track: ObservedTrack) -> list[tuple[float, float]]:
    points = []
    for wrist_index, elbow_index in ((L_WRIST, L_ELBOW), (R_WRIST, R_ELBOW)):
        wrist = keypoint(track, wrist_index)
        if wrist is None:
            continue
        elbow = keypoint(track, elbow_index)
        points.append(wrist if elbow is None else (wrist[0] + 0.35 * (wrist[0] - elbow[0]), wrist[1] + 0.35 * (wrist[1] - elbow[1])))
    return points


def touches(track: ObservedTrack, box, margin_rel: float = 0.05) -> bool:
    """A hand point lies inside the object region (expanded by 5% of person height) and the person is at the object's depth."""
    if not near(track, box, gap_rel=0.2):
        return False
    region = box_expand(box, margin_rel * box_height(track))
    return any(point_in_box(point, region) for point in hand_points(track))


def hip_midpoint(track: ObservedTrack):
    left, right = keypoint(track, L_HIP), keypoint(track, R_HIP)
    if left is None or right is None:
        return None
    return ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)


def torso_length(track: ObservedTrack):
    hips = hip_midpoint(track)
    shoulders = [p for p in (keypoint(track, L_SHOULDER), keypoint(track, R_SHOULDER)) if p is not None]
    if hips is None or not shoulders:
        return None, None
    mid = (sum(p[0] for p in shoulders) / len(shoulders), sum(p[1] for p in shoulders) / len(shoulders))
    return mid, hypot(hips[0] - mid[0], hips[1] - mid[1])


def seated_on(track: ObservedTrack, seat_box, other_seat_boxes=()) -> tuple[bool, tuple[float, float] | None, float]:
    """Single-frame seated-posture test against one seat. Returns (ok, hip midpoint, torso length).

    Rejects: hips hidden, a lying torso, hips outside the seat band, a nearer neighbouring seat, and straight legs
    (a standing person behind or beside the chair has knees about one torso length below the hips)."""
    hips = hip_midpoint(track)
    shoulders, torso = torso_length(track)
    if hips is None or shoulders is None or torso < 8:
        return False, None, 0.0
    if hips[1] - shoulders[1] < 0.6 * torso:
        return False, hips, torso
    x1, y1, x2, y2 = seat_box
    width, height = x2 - x1, y2 - y1
    band = (x1 - 0.1 * width, y1 + 0.2 * height, x2 + 0.1 * width, y1 + 0.85 * height)
    left, right = keypoint(track, L_HIP), keypoint(track, R_HIP)
    if not (point_in_box(left, band) and point_in_box(right, band)):
        return False, hips, torso
    own = hypot(hips[0] - box_center(seat_box)[0], hips[1] - box_center(seat_box)[1])
    if any(hypot(hips[0] - box_center(other)[0], hips[1] - box_center(other)[1]) < own for other in other_seat_boxes):
        return False, hips, torso
    for knee_index in (L_KNEE, R_KNEE):
        knee = keypoint(track, knee_index)
        if knee is not None and abs(knee[1] - hips[1]) > 0.6 * torso:
            return False, hips, torso
    return True, hips, torso
