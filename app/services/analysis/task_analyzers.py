from app.services.analysis.kinematics import range_of_motion


def aggregate_rom(angle_series: list[float]) -> dict[str, float]:
    min_angle, max_angle, rom = range_of_motion(angle_series)
    return {"min": min_angle, "max": max_angle, "rom": rom}
