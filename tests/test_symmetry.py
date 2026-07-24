from app.services.analysis.symmetry import SideRom, compute_symmetry, symmetry_index_score


def _side(rom, conf=0.9, frames=30):
    return SideRom(rom_deg=rom, mean_confidence=conf, valid_frames=frames)


def test_index_is_zero_for_equal_rom():
    assert symmetry_index_score(50.0, 50.0) == 0.0


def test_index_grows_with_imbalance():
    assert symmetry_index_score(60.0, 40.0) < symmetry_index_score(80.0, 20.0)


def test_index_is_one_when_one_side_is_still():
    assert symmetry_index_score(50.0, 0.0) == 1.0


def test_index_none_for_no_movement():
    assert symmetry_index_score(0.0, 0.0) is None


def test_both_legs_moving_yields_score():
    sides = {"left": _side(55.0), "right": _side(45.0)}
    # |55-45|/(55+45) = 0.1
    assert compute_symmetry(sides, participation_rom_deg=10.0) == 0.1


def test_unilateral_task_abstains():
    # Exercised leg sweeps a wide arc; the resting leg stays below participation.
    sides = {"left": _side(70.0), "right": _side(3.0)}
    assert compute_symmetry(sides, participation_rom_deg=10.0) is None


def test_missing_side_abstains():
    sides = {"right": _side(60.0)}
    assert compute_symmetry(sides, participation_rom_deg=10.0) is None


def test_too_few_valid_frames_abstains():
    sides = {"left": _side(50.0, frames=2), "right": _side(50.0, frames=30)}
    assert compute_symmetry(sides, participation_rom_deg=10.0) is None
