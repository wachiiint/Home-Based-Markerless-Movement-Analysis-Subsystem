"""2D->3D lifter interface and adapters.

``Lifter`` is the swap point (mirrors ``PoseEstimator``): any model that turns a
normalized H36M17 2D sequence into a 3D sequence plugs in here. The real model
is MotionBERT, loaded from an ONNX export; ``StubLifter`` exists only so the
conversion/normalization pipeline can be exercised in tests without weights.
"""

from pathlib import Path
from typing import Protocol

import numpy as np


class Lifter(Protocol):
    def lift(self, normalized_2d: np.ndarray, scores: np.ndarray) -> np.ndarray:
        """(T, 17, 2) normalized 2D + (T, 17) scores -> (T, 17, 3) root-relative 3D."""
        ...


class StubLifter:
    """Deterministic placeholder: z=0, passes 2D through. NOT a real lifter.

    Lets the end-to-end pipeline (convert -> normalize -> lift) be tested
    without MotionBERT weights. Never use for real analysis.
    """

    def lift(self, normalized_2d: np.ndarray, scores: np.ndarray) -> np.ndarray:
        normalized_2d = np.asarray(normalized_2d, dtype=np.float64)
        t, j, _ = normalized_2d.shape
        out = np.zeros((t, j, 3), dtype=np.float64)
        out[..., :2] = normalized_2d
        return out


class MotionBertAdapter:
    """Runs a MotionBERT ONNX export.

    Expected ONNX I/O (validate against the specific export before use):
        input  : float32 [1, T, 17, 3]  -> (x, y, confidence)
        output : float32 [1, T, 17, 3]  -> root-relative 3D
    """

    def __init__(self, model_path: str, backend: str = "onnxruntime") -> None:
        if not model_path or not Path(model_path).exists():
            raise FileNotFoundError(
                f"MotionBERT ONNX model not found at {model_path!r}; obtain/export the "
                "weights and set the path (see Phase C notes)."
            )
        import onnxruntime as ort

        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def lift(self, normalized_2d: np.ndarray, scores: np.ndarray) -> np.ndarray:
        normalized_2d = np.asarray(normalized_2d, dtype=np.float32)
        scores = np.asarray(scores, dtype=np.float32)
        t, j, _ = normalized_2d.shape
        model_in = np.zeros((1, t, j, 3), dtype=np.float32)
        model_in[0, :, :, :2] = normalized_2d
        model_in[0, :, :, 2] = scores
        out = self.session.run(None, {self.input_name: model_in})[0]
        return np.asarray(out[0], dtype=np.float64)
