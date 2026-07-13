LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16
LEFT_BIG_TOE = 17
LEFT_SMALL_TOE = 18
LEFT_HEEL = 19
RIGHT_BIG_TOE = 20
RIGHT_SMALL_TOE = 21
RIGHT_HEEL = 22

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


def get_keypoint(keypoints, index: int) -> tuple[float, float, float]:
    point = keypoints[index]
    return float(point[0]), float(point[1]), float(point[2])


def leg_indices(side: str) -> dict[str, int]:
    return LEFT_LEG if side == "left" else RIGHT_LEG
