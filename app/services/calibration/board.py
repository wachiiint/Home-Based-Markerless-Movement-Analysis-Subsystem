"""ChArUco board construction from a ``CharucoBoardSpec``.

Board geometry uses the *effective* square/marker size (nominal x print scale)
so that recovered translations and plane geometry are metric in millimetres.
"""

import cv2

from app.models.calibration import CharucoBoardSpec


def effective_square_length_mm(spec: CharucoBoardSpec, print_scale_factor: float) -> float:
    return spec.square_length_mm * print_scale_factor


def effective_marker_length_mm(spec: CharucoBoardSpec, print_scale_factor: float) -> float:
    return spec.marker_length_mm * print_scale_factor


def build_charuco_board(spec: CharucoBoardSpec, print_scale_factor: float = 1.0):
    """Return an OpenCV ``CharucoBoard`` sized in millimetres."""
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, spec.dictionary))
    return cv2.aruco.CharucoBoard(
        (spec.squares_x, spec.squares_y),
        effective_square_length_mm(spec, print_scale_factor),
        effective_marker_length_mm(spec, print_scale_factor),
        dictionary,
    )
