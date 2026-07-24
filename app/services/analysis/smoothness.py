"""Movement smoothness metrics from a joint-angle time series.

Single-camera-safe: these are derived purely from the angle trajectory over
time, so they need no force plate / ground-reaction force. All three are
established motor-control smoothness measures computed on the angular-*speed*
profile of the movement:

* ``sparc`` -- spectral arc length (Balasubramanian et al., 2015). Arc length of
  the normalized magnitude spectrum of the speed profile. Robust to noise and
  movement duration. More negative = less smooth.
* ``log_dimensionless_jerk`` (LDLJ) -- log of the amplitude/duration-normalized
  integral of squared jerk. Higher (closer to 0) = smoother.
* ``n_movement_units`` -- number of prominent peaks in the speed profile. One
  continuous motion is ~1; jerky, hesitant motion has many.

The series is the already-EMA-smoothed joint angle, sampled at a *uniform*
interval (1 / ``sample_fps``). Frames dropped for low confidence are treated as
contiguous, so these numbers are only meaningful when the valid-frame ratio is
high -- callers should surface them as decision support, not diagnosis.
"""

from __future__ import annotations

import numpy as np

_MIN_FRAMES = 8
_SPARC_FC = 10.0  # Hz: upper bound of the frequency band SPARC integrates over
_SPARC_AMP_TH = 0.05  # spectral magnitude below this is treated as noise floor
_UNIT_PROMINENCE = 0.05  # a speed peak counts if it exceeds 5% of the peak speed


def _sparc(speed: np.ndarray, fs: float, padlevel: int = 4) -> float | None:
    """Spectral arc length of a speed profile. Returns None if undefined."""
    n = speed.size
    if n < 2:
        return None
    nfft = int(2 ** (np.ceil(np.log2(n)) + padlevel))
    freq = np.arange(0, fs, fs / nfft)
    mag = np.abs(np.fft.fft(speed, nfft))
    peak = mag.max()
    if peak == 0:
        return None
    mag = mag / peak

    band = freq <= _SPARC_FC
    freq_sel = freq[band]
    mag_sel = mag[band]
    above = np.where(mag_sel >= _SPARC_AMP_TH)[0]
    if above.size < 2:
        return None
    lo, hi = int(above[0]), int(above[-1])
    freq_sel = freq_sel[lo : hi + 1]
    mag_sel = mag_sel[lo : hi + 1]
    span = freq_sel[-1] - freq_sel[0]
    if span == 0:
        return None
    arc = -np.sum(np.sqrt((np.diff(freq_sel) / span) ** 2 + np.diff(mag_sel) ** 2))
    return float(arc)


def _log_dimensionless_jerk(angle: np.ndarray, dt: float) -> float | None:
    """LDLJ of a joint-angle trajectory. Returns None if the motion is static."""
    amplitude = float(np.max(angle) - np.min(angle))
    if amplitude <= 1e-6:
        return None
    duration = dt * (angle.size - 1)
    if duration <= 0:
        return None
    vel = np.gradient(angle, dt)
    acc = np.gradient(vel, dt)
    jerk = np.gradient(acc, dt)
    integral = float(np.sum(jerk ** 2) * dt)  # deg^2 / s^5
    dimensionless = integral * duration ** 5 / amplitude ** 2  # dimensionless
    if dimensionless <= 0:
        return None
    return float(-np.log(dimensionless))


def _movement_units(speed: np.ndarray) -> int:
    """Count prominent local maxima in the speed profile."""
    peak = float(speed.max()) if speed.size else 0.0
    if peak <= 0:
        return 0
    threshold = _UNIT_PROMINENCE * peak
    count = 0
    for i in range(1, speed.size - 1):
        if speed[i] > speed[i - 1] and speed[i] >= speed[i + 1] and speed[i] >= threshold:
            count += 1
    return count


def compute_smoothness(angle_series: list[float], sample_fps: float, min_frames: int = _MIN_FRAMES) -> dict:
    """Smoothness metrics for one joint-angle time series.

    Returns an empty dict (best-effort: keeps the response field a placeholder)
    when there are too few frames or no measurable movement.
    """
    angle = np.asarray(angle_series, dtype=float)
    if angle.size < min_frames or sample_fps <= 0:
        return {}

    dt = 1.0 / float(sample_fps)
    speed = np.abs(np.gradient(angle, dt))

    sparc = _sparc(speed, float(sample_fps))
    ldlj = _log_dimensionless_jerk(angle, dt)
    units = _movement_units(speed)

    # No spectral/jerk signal AND no speed peaks -> effectively no movement.
    if sparc is None and ldlj is None and units == 0:
        return {}

    result: dict = {"n_movement_units": units, "n_samples": int(angle.size)}
    if sparc is not None:
        result["sparc"] = round(sparc, 4)
    if ldlj is not None:
        result["log_dimensionless_jerk"] = round(ldlj, 4)
    return result
