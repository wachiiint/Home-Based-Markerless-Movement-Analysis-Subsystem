import math


def angle_degrees(point_a, vertex, point_b) -> float:
    ax, ay = point_a
    vx, vy = vertex
    bx, by = point_b
    angle_a = math.atan2(ay - vy, ax - vx)
    angle_b = math.atan2(by - vy, bx - vx)
    diff = abs(math.degrees(angle_b - angle_a))
    return 360 - diff if diff > 180 else diff
