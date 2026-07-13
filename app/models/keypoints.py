# Halpe26 keypoint indices. See rtmlib's halpe26 skeleton definition for the
# authoritative order; indices 17-25 are head/neck/hip then the six foot points.
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16
HEAD = 17
NECK = 18
HIP = 19  # pelvis centre
LEFT_BIG_TOE = 20
RIGHT_BIG_TOE = 21
LEFT_SMALL_TOE = 22
RIGHT_SMALL_TOE = 23
LEFT_HEEL = 24
RIGHT_HEEL = 25

LEFT_LEG = {
    "shoulder": LEFT_SHOULDER,
    "hip": LEFT_HIP,
    "knee": LEFT_KNEE,
    "ankle": LEFT_ANKLE,
    "big_toe": LEFT_BIG_TOE,
}

RIGHT_LEG = {
    "shoulder": RIGHT_SHOULDER,
    "hip": RIGHT_HIP,
    "knee": RIGHT_KNEE,
    "ankle": RIGHT_ANKLE,
    "big_toe": RIGHT_BIG_TOE,
}


def get_keypoint(keypoints, index: int) -> tuple[float, float]:
    point = keypoints[index]
    return float(point[0]), float(point[1])


def leg_indices(side: str) -> dict[str, int]:
    return LEFT_LEG if side == "left" else RIGHT_LEG
