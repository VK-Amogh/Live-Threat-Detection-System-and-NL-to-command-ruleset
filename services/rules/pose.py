"""Optional person keypoints (YOLO pose), run only when an active rule needs them.

Weights are installed once by scripts/fetch_pose_weights.py and never downloaded at runtime. Without them, rules that need
a skeleton cannot activate and the runtime simply never loads this module's model."""

from pathlib import Path

from td_contracts import Observation
from .geometry import box_iou

SKELETON_MIN_POINTS = 5
SKELETON_MIN_CONF = 0.5
MATCH_IOU = 0.5


def skeleton_ok(keypoints) -> bool:
    """A coherent person: at least five confident points including a shoulder and the nose or a hip."""
    if not keypoints:
        return False
    confident = {index for index, (_, _, conf) in enumerate(keypoints) if conf >= SKELETON_MIN_CONF}
    return len(confident) >= SKELETON_MIN_POINTS and bool(confident & {5, 6}) and bool(confident & {0, 11, 12})


class PoseEstimator:
    def __init__(self, weights: Path, imgsz: int = 640, conf: float = 0.3):
        from ultralytics import YOLO
        self.model = YOLO(str(weights))
        self.imgsz = imgsz
        self.conf = conf

    @staticmethod
    def installed(weights: Path) -> bool:
        return weights.is_file()

    def attach(self, frame, observation: Observation) -> Observation:
        """Match pose detections to person tracks by box overlap and add keypoints. A person with no coherent skeleton is
        flagged `no_pose_support`; one with a skeleton loses the `oversized`/`border` flags (a real person very close to
        the camera, which the box gates alone cannot tell from a backpack close-up)."""
        people = [track for track in observation.tracks if track.cls == "person"]
        if not people:
            return observation
        result = self.model.predict(frame, imgsz=self.imgsz, conf=self.conf, verbose=False)[0]
        found = []
        if result.keypoints is not None and result.boxes is not None:
            boxes = result.boxes.xyxy.tolist()
            points = result.keypoints.data.tolist()
            found = [(tuple(box), [tuple(point) for point in kp]) for box, kp in zip(boxes, points)]
        updated, used = [], set()
        for track in observation.tracks:
            if track.cls != "person":
                updated.append(track)
                continue
            best, best_iou = None, MATCH_IOU
            for index, (box, _) in enumerate(found):
                overlap = box_iou(track.bbox, box)
                if index not in used and overlap >= best_iou:
                    best, best_iou = index, overlap
            if best is None:
                updated.append(track.model_copy(update={"flags": [*track.flags, "no_pose_support"]}))
                continue
            used.add(best)
            keypoints = found[best][1]
            if skeleton_ok(keypoints):
                flags = [flag for flag in track.flags if flag not in ("oversized", "border")]
                updated.append(track.model_copy(update={"keypoints": keypoints, "flags": [*flags, "pose_supported"]}))
            else:
                updated.append(track.model_copy(update={"keypoints": keypoints, "flags": [*track.flags, "no_pose_support"]}))
        return observation.model_copy(update={"tracks": updated})
