from typing import Protocol


class PoseEstimator(Protocol):
    def infer(self, frame):
        ...


class RtmlibAdapter:
    def __init__(self, device: str, mode: str, pose_model: str, backend: str = "onnxruntime") -> None:
        self.device = device
        self.mode = mode
        self.pose_model = pose_model
        from rtmlib import BodyWithFeet

        # The project config calls this integration "rtmlib"; rtmlib's
        # concrete inference backend is ONNX Runtime.
        backend = "onnxruntime" if backend == "rtmlib" else backend

        self.model = BodyWithFeet(
            mode=mode,
            backend=backend,
            device=device,
        )

    def infer(self, frame):
        return self.model(frame)


class MmposeAdapter:
    def infer(self, frame):
        raise NotImplementedError("MMPose is optional and not implemented in v1.")
