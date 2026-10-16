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
    a, b = line
    first = _orientation(a, b, previous)
    second = _orientation(a, b, current)
    if first == 0 or second == 0 or first * second >= 0:
        return False
    third = _orientation(previous, current, a)
    fourth = _orientation(previous, current, b)
    return third * fourth <= 0


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
