from pathlib import Path

import numpy as np
import pytest

from app.services.lifting.lifter import (
    MotionBertAdapter,
    StubLifter,
    build_lifter,
    validate_lifter_io,
)


def test_build_lifter_disabled_returns_none():
    assert build_lifter(enable_3d=False, model_path="anything.onnx") is None


def test_build_lifter_missing_weights_returns_none():
    # enabled but no weights -> graceful None (2D fallback), never raises
    assert build_lifter(enable_3d=True, model_path="does/not/exist.onnx") is None


def test_validate_lifter_io_accepts_good_lifter():
    validate_lifter_io(StubLifter())  # shape (T,17,3), finite -> no raise


class _BadShapeLifter:
    def lift(self, normalized_2d, scores):
        t = normalized_2d.shape[0]
        return np.zeros((t, 17, 2))  # wrong: 2 dims, not 3


class _NonFiniteLifter:
    def lift(self, normalized_2d, scores):
        t = normalized_2d.shape[0]
        out = np.zeros((t, 17, 3))
        out[0, 0, 0] = np.nan
        return out


def test_validate_lifter_io_rejects_wrong_shape():
    with pytest.raises(ValueError):
        validate_lifter_io(_BadShapeLifter())


def test_validate_lifter_io_rejects_non_finite():
    with pytest.raises(ValueError):
        validate_lifter_io(_NonFiniteLifter())


class _PassThroughChunkAdapter(MotionBertAdapter):
    """MotionBertAdapter windowing logic with the ONNX pass replaced by an
    identity: each window returns its own 2D unchanged (z=0). A correct
    overlap-blend must then reconstruct the full input exactly."""

    def __init__(self, max_frames: int, overlap: int) -> None:
        self.max_frames = max_frames
        self.overlap = overlap

    def _run(self, normalized_2d, scores):
        t, j, _ = normalized_2d.shape
        out = np.zeros((t, j, 3), dtype=np.float64)
        out[..., :2] = normalized_2d
        return out


def test_lift_chunking_reconstructs_long_sequence():
    rng = np.random.default_rng(0)
    t = 600  # > max_frames -> forces multiple windows
    normalized_2d = rng.standard_normal((t, 17, 2))
    scores = np.ones((t, 17))
    adapter = _PassThroughChunkAdapter(max_frames=243, overlap=32)

    out = adapter.lift(normalized_2d, scores)

    assert out.shape == (t, 17, 3)
    assert np.isfinite(out).all()
    # blend of identical per-window values must be lossless everywhere
    np.testing.assert_allclose(out[..., :2], normalized_2d, rtol=0, atol=1e-5)


def test_lift_short_sequence_is_single_pass():
    normalized_2d = np.random.default_rng(1).standard_normal((100, 17, 2))
    scores = np.ones((100, 17))
    adapter = _PassThroughChunkAdapter(max_frames=243, overlap=32)
    out = adapter.lift(normalized_2d, scores)
    assert out.shape == (100, 17, 3)
    np.testing.assert_allclose(out[..., :2], normalized_2d, rtol=0, atol=1e-5)


_MODEL_PATH = Path("models/motionbert_lite.onnx")


@pytest.mark.skipif(not _MODEL_PATH.exists(), reason="MotionBERT ONNX weights not present")
def test_real_model_handles_over_maxlen_sequence():
    adapter = MotionBertAdapter(str(_MODEL_PATH))
    t = adapter.max_frames + 60
    normalized_2d = np.random.default_rng(2).standard_normal((t, 17, 2)).astype(np.float32) * 0.1
    scores = np.ones((t, 17), dtype=np.float32)
    out = adapter.lift(normalized_2d, scores)
    assert out.shape == (t, 17, 3)
    assert np.isfinite(out).all()
