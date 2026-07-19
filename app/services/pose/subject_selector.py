def select_main_subject(poses):
    if not poses:
        return None
    return max(poses, key=lambda pose: float(pose[1].mean()) if len(pose[1]) else 0.0)
