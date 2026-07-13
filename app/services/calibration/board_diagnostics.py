"""Classify why ChArUco board detection failed, for clinician review.

Runs on cheap per-frame signals (brightness, blur, how many markers/corners
were ever seen) accumulated during the analysis pass. Advisory only.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.models.calibration import BoardDetectionDiagnostics
from app.services.calibration.charuco_calibrator import MIN_POSE_CORNERS

# thresholds on an 8-bit grayscale frame
DARK_BRIGHTNESS = 40.0
BRIGHT_BRIGHTNESS = 220.0
BLUR_VARIANCE = 100.0  # variance of Laplacian below this reads as blurry
SMALL_CORNERS = MIN_POSE_CORNERS  # some markers but too few corners to pose


def frame_brightness(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(gray.mean())


def frame_blur_score(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


@dataclass
class BoardObservationStats:
    """Accumulated per-frame signals used to build the diagnostics."""

    frames_checked: int = 0
    frames_with_any_marker: int = 0
    max_corners_found: int = 0
    brightness_samples: list[float] = field(default_factory=list)
    blur_samples: list[float] = field(default_factory=list)

    def update(self, n_markers: int, n_corners: int, brightness: float, blur: float) -> None:
        self.frames_checked += 1
        if n_markers > 0:
            self.frames_with_any_marker += 1
        self.max_corners_found = max(self.max_corners_found, n_corners)
        self.brightness_samples.append(brightness)
        self.blur_samples.append(blur)


def build_diagnostics(stats: BoardObservationStats, detected: bool) -> BoardDetectionDiagnostics:
    brightness = float(np.mean(stats.brightness_samples)) if stats.brightness_samples else 0.0
    blur = float(np.median(stats.blur_samples)) if stats.blur_samples else 0.0

    causes: list[str] = []
    if not detected:
        if brightness < DARK_BRIGHTNESS:
            causes.append("too_dark")
        elif brightness > BRIGHT_BRIGHTNESS:
            causes.append("overexposed")
        if blur < BLUR_VARIANCE:
            causes.append("motion_blur")
        if stats.frames_with_any_marker == 0:
            # no marker ever seen and lighting looked ok -> board likely absent/wrong
            if not causes:
                causes.append("board_absent")
        else:
            # markers seen but never enough corners to pose
            if 0 < stats.max_corners_found < SMALL_CORNERS:
                causes.append("partial_occlusion_or_too_far")
            if stats.frames_with_any_marker < stats.frames_checked / 2:
                causes.append("intermittent_occlusion")
        if not causes:
            causes.append("board_not_recognized")

    if detected:
        recommendation, message = "ok", "ChArUco board detected; 3D calibration available."
    else:
        recommendation = "retake"
        message = "Board not usable for 3D (" + ", ".join(causes) + "). Consider a re-record; 2D analysis still provided."

    return BoardDetectionDiagnostics(
        detected=detected,
        frames_checked=stats.frames_checked,
        frames_with_any_marker=stats.frames_with_any_marker,
        max_corners_found=stats.max_corners_found,
        brightness_mean=round(brightness, 2),
        blur_score=round(blur, 2),
        likely_causes=causes,
        recommendation=recommendation,
        message=message,
    )
