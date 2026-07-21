"""Compute and store a device's intrinsics from board footage.

This is the missing entry point that lets the metric-3D path run at all: until a
device has a ``valid`` ``DeviceIntrinsics`` record, ``SessionCalibrator.finalize``
returns "device not calibrated" and analysis stays 2D.

Feed it a short video (or a folder of stills) of the printed board held at
several angles/distances. It samples frames, runs the real ChArUco detection +
``cv2.calibrateCamera``, folds in the printed-scale correction from the 100 mm
reference bar, and writes the record keyed by ``device_id``.

Run with ``python -m app.tools.calibrate_device --video calib.mp4 --make Apple
--model "iPhone 13" --measured-bar-mm 99``.
"""

import argparse
import glob
from pathlib import Path

import cv2
import numpy as np

from app.core.config import get_settings
from app.models.calibration import CharucoBoardSpec
from app.services.calibration.charuco_calibrator import calibrate_device_from_images
from app.services.calibration.device_id import derive_device_id
from app.services.calibration.device_store import DeviceStore
from app.services.calibration.print_verify import compute_print_scale


def sample_video_frames(path: Path, sample_fps: float, max_frames: int) -> tuple[list[np.ndarray], tuple[int, int]]:
    """Grab up to ``max_frames`` frames at ``sample_fps`` and the (w, h) size."""
    capture = cv2.VideoCapture(str(path))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        interval = max(1, round(fps / sample_fps))
        frames: list[np.ndarray] = []
        index = 0
        while len(frames) < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            if index % interval == 0:
                frames.append(frame)
            index += 1
    finally:
        capture.release()
    return frames, (width, height)


def load_image_frames(pattern: str) -> tuple[list[np.ndarray], tuple[int, int]]:
    frames = [img for p in sorted(glob.glob(pattern)) if (img := cv2.imread(p)) is not None]
    if not frames:
        raise ValueError(f"no readable images matched {pattern!r}")
    height, width = frames[0].shape[:2]
    return frames, (width, height)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate a device's intrinsics from board footage.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path, help="video of the board at several angles")
    source.add_argument("--images", type=str, help="glob of board still images (e.g. 'shots/*.jpg')")
    parser.add_argument("--make", default="", help="camera make (improves device_id stability)")
    parser.add_argument("--model", default="", help="camera model")
    parser.add_argument("--measured-bar-mm", type=float, default=100.0, help="measured length of the printed 100 mm bar")
    parser.add_argument("--data-dir", type=Path, default=None, help="calibration store dir (default: settings)")
    parser.add_argument("--sample-fps", type=float, default=2.0, help="frames/sec to sample from --video")
    parser.add_argument("--max-frames", type=int, default=40, help="cap on views fed to calibrateCamera")
    args = parser.parse_args(argv)

    if args.video is not None:
        frames, image_size = sample_video_frames(args.video, args.sample_fps, args.max_frames)
    else:
        frames, image_size = load_image_frames(args.images)
    if not frames:
        print("no frames to calibrate from")
        return 1

    print_scale_factor, scale_warnings = compute_print_scale(args.measured_bar_mm)
    for warning in scale_warnings:
        print(f"warning: {warning}")

    orientation = "portrait" if image_size[1] >= image_size[0] else "landscape"
    meta = {"make": args.make, "model": args.model, "width": image_size[0], "height": image_size[1], "orientation": orientation}
    device_id, source_label = derive_device_id(meta)

    spec = CharucoBoardSpec()
    intrinsics = calibrate_device_from_images(
        frames, device_id=device_id, image_size=image_size, spec=spec,
        print_scale_factor=print_scale_factor, raw_meta=meta, source=source_label,
    )

    if intrinsics.status != "valid":
        print(f"calibration FAILED (status={intrinsics.status}); need >=3 frames with the board clearly visible")
        print(f"  frames sampled: {len(frames)}  device_id: {device_id}  metadata source: {source_label}")
        return 1

    data_dir = args.data_dir or Path(get_settings().calibration_data_dir)
    DeviceStore(data_dir).put(intrinsics)
    print(f"calibrated device_id={device_id} (metadata source: {source_label})")
    print(f"  image_size={image_size}  reproj RMS={intrinsics.reproj_error_px:.3f}px  print_scale_factor={print_scale_factor:.4f}")
    print(f"  stored in {data_dir}")
    if source_label == "resolution_only":
        print("  note: no make/model given -> id keyed on resolution only; two phones at this resolution will collide")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
