import numpy as np

from app.services.calibration.board_diagnostics import (
    BoardObservationStats,
    build_diagnostics,
    frame_blur_score,
    frame_brightness,
)


def test_frame_brightness_extremes():
    assert frame_brightness(np.zeros((10, 10, 3), np.uint8)) == 0.0
    assert frame_brightness(np.full((10, 10, 3), 255, np.uint8)) == 255.0


def test_blur_score_sharp_gt_flat():
    flat = np.zeros((32, 32), np.uint8)
    sharp = np.zeros((32, 32), np.uint8)
    sharp[:, ::2] = 255  # high-frequency stripes
    assert frame_blur_score(sharp) > frame_blur_score(flat)


def test_diagnostics_detected_ok():
    stats = BoardObservationStats()
    stats.update(n_markers=20, n_corners=40, brightness=120, blur=500)
    diag = build_diagnostics(stats, detected=True)
    assert diag.detected
    assert diag.recommendation == "ok"


def test_diagnostics_too_dark():
    stats = BoardObservationStats()
    for _ in range(5):
        stats.update(n_markers=0, n_corners=0, brightness=15, blur=500)
    diag = build_diagnostics(stats, detected=False)
    assert "too_dark" in diag.likely_causes
    assert diag.recommendation == "retake"


def test_diagnostics_board_absent_when_lit_but_no_markers():
    stats = BoardObservationStats()
    for _ in range(5):
        stats.update(n_markers=0, n_corners=0, brightness=130, blur=500)
    diag = build_diagnostics(stats, detected=False)
    assert "board_absent" in diag.likely_causes


def test_diagnostics_partial_when_markers_but_few_corners():
    stats = BoardObservationStats()
    for _ in range(5):
        stats.update(n_markers=2, n_corners=2, brightness=130, blur=500)
    diag = build_diagnostics(stats, detected=False)
    assert "partial_occlusion_or_too_far" in diag.likely_causes
