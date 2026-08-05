import math

from app.services.analysis.outliers import half_window_for, reject_outliers


def _sweep(n=60, amplitude=60.0, cycles=3.0):
    """A clean multi-repetition flexion series: the recorded protocol asks for at
    least three reps, which is what makes single-frame spikes rejectable.

    Defaults model a 6 s clip at FRAME_SAMPLE_FPS=10 with three ~2 s reps, i.e.
    20 samples per repetition.
    """
    return [90.0 + amplitude * math.sin(2 * math.pi * cycles * i / n) for i in range(n)]


def test_clean_sweep_is_left_alone():
    values = _sweep()
    report = reject_outliers(values, half_window=3)
    assert report.replaced_count == 0
    assert report.values == values


def test_linear_ramp_survives():
    # A centred median reproduces a ramp exactly -- genuine fast motion must not
    # be mistaken for a spike.
    values = [10.0 * i for i in range(20)]
    assert reject_outliers(values, half_window=3).replaced_count == 0


def test_single_frame_swap_is_repaired():
    values = _sweep()
    values[17] = 178.0  # the other (straight) leg's angle for one frame
    report = reject_outliers(values, half_window=3)
    assert report.replaced_indices == [17]
    assert abs(report.values[17] - 178.0) > 40  # replaced by the local median


def test_spike_no_longer_inflates_rom():
    from app.services.analysis.kinematics import range_of_motion

    values = _sweep()  # true ROM is ~120 deg
    values[17] = 178.0
    _, _, dirty_rom = range_of_motion(values)
    _, _, clean_rom = range_of_motion(reject_outliers(values, half_window=3).values)
    assert dirty_rom > clean_rom
    assert abs(clean_rom - 120.0) < 5.0


def test_stationary_leg_is_not_shredded():
    # A resting limb has ~0 local spread; without the min-scale floor every
    # sub-degree wobble would read as an outlier.
    values = [180.0, 179.6, 180.2, 179.8, 180.1, 179.9, 180.0, 180.3, 179.7, 180.0]
    assert reject_outliers(values, half_window=3).replaced_count == 0


def test_stationary_leg_still_catches_a_real_spike():
    values = [180.0] * 10
    values[5] = 120.0
    assert reject_outliers(values, half_window=3).replaced_indices == [5]


def test_short_series_is_returned_untouched():
    values = [10.0, 90.0, 11.0]
    report = reject_outliers(values, half_window=3)
    assert report.values == values and report.replaced_count == 0


def test_empty_series():
    report = reject_outliers([], half_window=3)
    assert report.values == [] and report.replaced_ratio() == 0.0


def test_known_limit_very_fast_reps_touch_the_edges():
    """Documented limit, not desired behaviour.

    Below roughly 15 samples per repetition the window spans a large part of a
    cycle, and the truncated window at the series ends biases the local median
    enough to repair a genuine sample. It costs one endpoint value, replaced by
    a nearby median, so ROM moves only slightly -- but record it so a future
    change to the window size is a deliberate one.
    """
    fast = _sweep(n=40, cycles=3.0)  # 13.3 samples per rep
    assert reject_outliers(fast, half_window=3).replaced_indices == [39]


def test_window_scales_with_sample_rate():
    assert half_window_for(10, 0.3) == 3
    assert half_window_for(30, 0.3) == 9
    assert half_window_for(2, 0.3) == 1  # never degenerates to 0
