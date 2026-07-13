def screen_rom(
    *,
    rom_deg: float,
    expected_rom_deg: float,
    borderline_rom_deg: float,
    valid_frame_ratio: float,
    min_valid_frame_ratio: float,
    mean_keypoint_confidence: float,
) -> tuple[str, float, list[str]]:
    flags: list[str] = []
    if valid_frame_ratio < min_valid_frame_ratio:
        flags.append("low_valid_frame_ratio")
    if mean_keypoint_confidence < 0.5:
        flags.append("low_keypoint_confidence")

    if flags or rom_deg < borderline_rom_deg:
        risk = "high"
    elif rom_deg < expected_rom_deg:
        risk = "moderate"
    else:
        risk = "low"

    confidence = max(0.0, min(1.0, 0.5 * valid_frame_ratio + 0.5 * mean_keypoint_confidence))
    return risk, confidence, flags
