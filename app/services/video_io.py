from fastapi import UploadFile
from pathlib import Path
import shutil
import tempfile

import cv2


async def validate_video_upload(file: UploadFile) -> None:
    head = await file.read(16)
    await file.seek(0)
    if not head:
        raise ValueError("unreadable video")


async def save_upload(file: UploadFile, max_bytes: int) -> Path:
    if file.size is not None and file.size > max_bytes:
        raise ValueError("video is too large")
    directory = Path(tempfile.mkdtemp(prefix="rtmpose-upload-"))
    suffix = Path(file.filename or "upload.mp4").suffix.lower() or ".mp4"
    destination = directory / f"input{suffix}"
    total = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("video is too large")
                output.write(chunk)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return destination


def read_video_metadata(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("unreadable video")
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
            raise ValueError("unreadable video")
        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_sec": frame_count / fps,
        }
    finally:
        capture.release()
