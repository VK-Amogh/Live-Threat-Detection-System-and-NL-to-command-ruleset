"""Camera pixel geometry and calibrated ground-plane distances."""

from math import hypot


def in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def crosses_line(previous, current, line) -> bool:
    """True when the step previous -> current passes through the line segment.

    A point exactly on the line counts as being on the positive side, so a track that lands precisely on the line
    and carries on across it is still detected (treating 0 as "neither side" lost those crossings)."""
    a, b = line
    first_positive = _orientation(a, b, previous) >= 0
    second_positive = _orientation(a, b, current) >= 0
    if first_positive == second_positive:
        return False
    third = _orientation(previous, current, a)
    fourth = _orientation(previous, current, b)
    return third * fourth <= 0


def cross_direction(previous, current, line) -> str | None:
    """Direction of a crossing: 'a_to_b' when the step goes from the negative side (A) to the non-negative side (B).

    The B side lies along the normal (-dy, dx) of the line vector, which is what the dashboard draws as the arrow."""
    if not crosses_line(previous, current, line):
        return None
    return "a_to_b" if _orientation(line[0], line[1], previous) < 0 else "b_to_a"


def centroid(polygon):
    return (sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon))


def homography_point(point, matrix):
    x, y = point
    scale = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
    if abs(scale) < 1e-9:
        raise ValueError("homography maps point to infinity")
    return ((matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]) / scale,
            (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]) / scale)


def distance_to_polygon(point, polygon):
    if in_polygon(point, polygon):
        return 0.0
    distances = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        denominator = dx * dx + dy * dy
        t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denominator)) if denominator else 0
        distances.append(hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy)))
    return min(distances)


# --- axis-aligned box helpers (x1, y1, x2, y2) -------------------------------------------------------------------

def box_area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def box_intersection(a, b) -> float:
    return box_area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def box_iou(a, b) -> float:
    inter = box_intersection(a, b)
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def box_coverage(box, region) -> float:
    """Share of `region` that `box` covers."""
    area = box_area(region)
    return box_intersection(box, region) / area if area > 0 else 0.0


def box_gap(a, b) -> float:
    """Shortest pixel distance between two boxes (0 when they touch or overlap)."""
    return hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))


def box_expand(box, margin: float):
    return (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)


def point_in_box(point, box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def box_center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
