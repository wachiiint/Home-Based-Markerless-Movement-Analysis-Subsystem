# Halpe26 keypoint indices. See rtmlib's halpe26 skeleton definition for the
# authoritative order; indices 17-25 are head/neck/hip then the six foot points.
NOSE = 0
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10
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

# Names in index order, for self-describing exports. Indices 1-4 (eyes, ears)
# have no named constant above because nothing in the analysis reads them, but
# they are part of the 26-point set and are still exported.
HALPE26_JOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
    "head", "neck", "pelvis",
    "left_big_toe", "right_big_toe", "left_small_toe", "right_small_toe",
    "left_heel", "right_heel",
]

# Bone connectivity (a, b) for drawing the 2D skeleton, following rtmlib's
# halpe26 link set. Only needed by exports and external viewers -- the annotated
# MP4 is drawn by rtmlib's own draw_skeleton, which carries its own copy.
HALPE26_EDGES: list[tuple[int, int]] = [
    (0, 1), (0, 2), (1, 3), (2, 4),            # face
    (HEAD, NECK), (NECK, HIP),                 # head -> neck -> pelvis
    (NECK, LEFT_SHOULDER), (NECK, RIGHT_SHOULDER),
    (LEFT_SHOULDER, LEFT_ELBOW), (LEFT_ELBOW, LEFT_WRIST),
    (RIGHT_SHOULDER, RIGHT_ELBOW), (RIGHT_ELBOW, RIGHT_WRIST),
    (HIP, LEFT_HIP), (HIP, RIGHT_HIP),
    (LEFT_HIP, LEFT_KNEE), (LEFT_KNEE, LEFT_ANKLE),
    (RIGHT_HIP, RIGHT_KNEE), (RIGHT_KNEE, RIGHT_ANKLE),
    (LEFT_ANKLE, LEFT_HEEL), (LEFT_ANKLE, LEFT_BIG_TOE), (LEFT_ANKLE, LEFT_SMALL_TOE),
    (RIGHT_ANKLE, RIGHT_HEEL), (RIGHT_ANKLE, RIGHT_BIG_TOE), (RIGHT_ANKLE, RIGHT_SMALL_TOE),
]


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


def leg_indices(side: str) -> dict[str, int]:
    return LEFT_LEG if side == "left" else RIGHT_LEG
