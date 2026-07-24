import numpy as np

from app.services.analysis.smoothness import compute_smoothness

FPS = 15.0


def _smooth_flexion(n: int = 45, amplitude: float = 60.0) -> list[float]:
    """One clean minimum-jerk-like flexion+extension (a single raised cosine)."""
    t = np.linspace(0.0, 1.0, n)
    return (amplitude * (0.5 - 0.5 * np.cos(2 * np.pi * t))).tolist()


def _jerky_flexion(n: int = 45, amplitude: float = 60.0) -> list[float]:
    """Same endpoints/amplitude but hesitant: a staircase with tremor added."""
    base = np.asarray(_smooth_flexion(n, amplitude))
    tremor = 6.0 * np.sin(2 * np.pi * 5.0 * np.linspace(0.0, 1.0, n))  # 5 Hz wobble
    steps = np.round(base / 12.0) * 12.0  # quantize into abrupt jumps
    return (steps + tremor).tolist()


def test_returns_empty_for_too_few_frames():
    assert compute_smoothness([1.0, 2.0, 3.0], FPS) == {}


def test_returns_empty_for_no_movement():
    assert compute_smoothness([30.0] * 40, FPS) == {}


def test_reports_expected_keys():
    result = compute_smoothness(_smooth_flexion(), FPS)
    assert set(result) >= {"sparc", "log_dimensionless_jerk", "n_movement_units", "n_samples"}
    assert result["n_samples"] == 45


def test_smooth_motion_scores_smoother_than_jerky():
    smooth = compute_smoothness(_smooth_flexion(), FPS)
    jerky = compute_smoothness(_jerky_flexion(), FPS)

    # SPARC: less negative = smoother
    assert smooth["sparc"] > jerky["sparc"]
    # LDLJ: higher (closer to 0) = smoother
    assert smooth["log_dimensionless_jerk"] > jerky["log_dimensionless_jerk"]
    # A single motion has few speed peaks; the jerky staircase has many more
    assert smooth["n_movement_units"] < jerky["n_movement_units"]


def test_single_flexion_is_roughly_one_or_two_units():
    result = compute_smoothness(_smooth_flexion(), FPS)
    assert 1 <= result["n_movement_units"] <= 2
