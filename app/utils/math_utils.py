import math


def angle_degrees(point_a, vertex, point_b) -> float:
    ax, ay = point_a
    vx, vy = vertex
    bx, by = point_b
    angle_a = math.atan2(ay - vy, ax - vx)
    angle_b = math.atan2(by - vy, bx - vx)
    diff = abs(math.degrees(angle_b - angle_a))
    return 360 - diff if diff > 180 else diff


def vector_angle_degrees(point_a, vertex, point_b) -> float:
    """Interior angle a-vertex-b for points of any dimension (2D or 3D).

    Uses the dot-product form, so it generalises the 2D ``angle_degrees`` to the
    lifted 3D skeleton. Returns a value in [0, 180]; 0 if a ray has zero length.
    """
    a = [pa - pv for pa, pv in zip(point_a, vertex)]
    b = [pb - pv for pb, pv in zip(point_b, vertex)]
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return math.degrees(math.acos(cosine))
