import numpy as np
import pytest

from app.services.lifting.lifter import StubLifter, build_lifter, validate_lifter_io


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
