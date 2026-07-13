from app.utils.math_utils import angle_degrees


def three_point_angle(point_a, vertex, point_b) -> float:
    return angle_degrees(point_a, vertex, point_b)


def range_of_motion(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    min_value = min(values)
    max_value = max(values)
    return min_value, max_value, round(max_value - min_value, 2)
