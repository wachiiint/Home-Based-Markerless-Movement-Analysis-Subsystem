"""Derive a stable per-device id from capture metadata.

``K`` depends on resolution + orientation, not just the phone model, so the id
composes all of them. make/model come from EXIF/container tags when present;
video often lacks them, so the id degrades gracefully and records ``source`` so
callers can see how much metadata backed it.
"""

import hashlib

import cv2


def derive_device_id(meta: dict) -> tuple[str, str]:
    """Return (device_id, source).

    ``meta`` keys: make, model, width, height, orientation. Missing make/model
    contribute empty strings; two different phones at the same resolution will
    then collide (source="resolution_only") -- an accepted, logged limitation.
    """
    make = str(meta.get("make", "") or "").strip().lower()
    model = str(meta.get("model", "") or "").strip().lower()
    width = int(meta.get("width", 0) or 0)
    height = int(meta.get("height", 0) or 0)
    orientation = str(meta.get("orientation", "") or "").strip().lower()

    if make or model:
        source = "full" if (make and model) else "partial"
    else:
        source = "resolution_only"

    key = f"{make}|{model}|{width}x{height}|{orientation}"
    device_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return device_id, source


def extract_capture_metadata(path) -> dict:
    """Best-effort metadata from a video file.

    Resolution/orientation come reliably from OpenCV. make/model are left empty
    here (MP4 tag parsing is out of scope for Phase B); a caller may supply them
    from client-provided upload headers and merge into this dict.
    """
    capture = cv2.VideoCapture(str(path))
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    orientation = "portrait" if height >= width else "landscape"
    return {"make": "", "model": "", "width": width, "height": height, "orientation": orientation}
