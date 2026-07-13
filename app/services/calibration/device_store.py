"""Persistence for ``DeviceIntrinsics``, keyed by device_id.

A device's ``K`` is only valid at the resolution it was calibrated for, so a
lookup that supplies a different ``image_size`` returns the record marked
``stale`` rather than silently reusing a wrong ``K``.
"""

import json
from pathlib import Path

from app.models.calibration import DeviceIntrinsics


class DeviceStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "device_intrinsics.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def put(self, intrinsics: DeviceIntrinsics) -> None:
        data = self._load()
        data[intrinsics.device_id] = intrinsics.model_dump()
        self._save(data)

    def get(self, device_id: str, image_size: tuple[int, int] | None = None) -> DeviceIntrinsics | None:
        data = self._load()
        record = data.get(device_id)
        if record is None:
            return None
        intrinsics = DeviceIntrinsics(**record)
        if image_size is not None and tuple(intrinsics.image_size) != tuple(image_size):
            intrinsics.status = "stale"
        return intrinsics
