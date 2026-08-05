"""Spike rejection for joint-angle series (Hampel filter).

Why this exists: RTMPose occasionally assigns the left keypoints to the right
limb for a few frames. The pose still looks plausible, so no confidence
threshold catches it, but the angle series jumps to the *other* leg's angle and
back. ``range_of_motion`` takes a min and a max, so a single such frame is
enough to corrupt the reported ROM -- and ROM is what drives screening.

The recorded protocol asks for at least three repetitions per clip, so the
genuine extremes are visited repeatedly. A value that appears once and reverts
is therefore safe to treat as a tracking artefact rather than as movement.

**Local, not global.** A whole-series median/MAD test is wrong here: a real
sweep is *supposed* to have a wide spread, so a global test either rejects the
genuine peaks or nothing at all. What marks an artefact is that it disagrees
with its immediate *neighbours in time*. The Hampel filter is exactly that test
-- median and MAD over a short sliding window -- so a linear sweep passes
through untouched (a centred median reproduces a ramp exactly) while a spike
against the local trend stands out.

Outliers are **replaced with the local median rather than dropped**, keeping the
series uniformly sampled. Smoothness (LDLJ, SPARC) differentiates the series and
assumes a fixed timestep, so deleting samples would silently distort it.

**What this does not catch.** A swap lasting longer than the window half-width
becomes the local median itself and passes. Sustained mistracking needs a
geometric left/right consistency check on the keypoints, not a statistical test
on the angles.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

# Scales the MAD to be a consistent estimator of the standard deviation for
# normally distributed data -- the constant that makes ``n_sigma`` mean sigma.
_MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class OutlierReport:
    """Cleaned series plus what had to be repaired to get it."""

    values: list[float]
    replaced_indices: list[int]

    @property
    def replaced_count(self) -> int:
        return len(self.replaced_indices)

    def replaced_ratio(self) -> float:
        return len(self.replaced_indices) / len(self.values) if self.values else 0.0


def reject_outliers(
    values: list[float],
    half_window: int = 3,
    n_sigma: float = 3.0,
    min_scale: float = 2.0,
) -> OutlierReport:
    """Replace samples that disagree with their local neighbourhood.

    ``half_window`` is in samples either side, so the window spans
    ``2 * half_window + 1``. ``min_scale`` floors the local spread estimate, in
    the same unit as ``values`` (degrees): without it a stationary limb has a
    local MAD of ~0 and every sub-degree wobble reads as an outlier.
    """
    n = len(values)
    if n < 2 * half_window + 1 or half_window < 1:
        # Too short for a meaningful neighbourhood -- leave it alone rather than
        # judge a sample against one or two others.
        return OutlierReport(values=list(values), replaced_indices=[])

    cleaned = list(values)
    replaced: list[int] = []
    for i in range(n):
        window = values[max(0, i - half_window) : min(n, i + half_window + 1)]
        local_median = median(window)
        scale = max(_MAD_TO_SIGMA * median([abs(v - local_median) for v in window]), min_scale)
        if abs(values[i] - local_median) > n_sigma * scale:
            cleaned[i] = local_median
            replaced.append(i)
    return OutlierReport(values=cleaned, replaced_indices=replaced)


def half_window_for(sampled_fps: int, seconds: float = 0.3) -> int:
    """Window half-width in samples for a given time span, at least 1.

    Sized in time, not frames, so the filter behaves the same whichever
    ``FRAME_SAMPLE_FPS`` the service runs at. The default spans ~0.6 s, short
    enough to sit inside one repetition of a limb movement.
    """
    return max(1, round(sampled_fps * seconds))
