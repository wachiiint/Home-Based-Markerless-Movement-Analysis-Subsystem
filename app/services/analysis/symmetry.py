"""Left/right movement symmetry from per-leg range of motion.

Single-camera-safe: derived purely from the two legs' joint-angle ROM, so it
needs no force plate / ground-reaction force. Reports a normalized asymmetry
index in ``[0, 1]``::

    symmetry_index_score = |ROM_left - ROM_right| / (ROM_left + ROM_right)

``0.0`` means the two legs swept an identical range (perfectly symmetric);
values toward ``1.0`` mean one leg did nearly all of the moving. This is the
Robinson & Herzog (1987) Symmetry Index rescaled from a percentage onto the unit
interval (``SI% = score * 200``), which keeps the number bounded and matches the
``symmetry_index_score`` contract field's scale.

Only defined when BOTH legs actually performed the movement. The v1 task set is
unilateral -- one leg exercises while the other rests -- so comparing an
exercised leg against a resting one would report a spurious ~1.0 every time. In
that case the score abstains (``None``) and stays a placeholder, matching the
other not-yet-populated ``clinical_metrics`` fields. It becomes meaningful only
for a clip in which both legs perform the same task (e.g. a future bilateral
task, or a patient who exercises both sides in one recording).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SideRom:
    """Whole-clip motion summary for one leg."""

    rom_deg: float
    mean_confidence: float
    valid_frames: int


_MIN_SIDE_VALID_FRAMES = 4


def _participated(side: SideRom | None, participation_rom_deg: float, min_valid_frames: int) -> bool:
    """A leg counts as performing the movement only if it was tracked over
    enough frames AND swept at least the task's participation ROM."""
    return (
        side is not None
        and side.valid_frames >= min_valid_frames
        and side.rom_deg >= participation_rom_deg
    )


def symmetry_index_score(left_rom: float, right_rom: float) -> float | None:
    """Normalized asymmetry of two ROM values. None if both are zero."""
    total = left_rom + right_rom
    if total <= 0:
        return None
    return round(abs(left_rom - right_rom) / total, 4)


def compute_symmetry(
    sides: dict[str, SideRom],
    participation_rom_deg: float,
    min_valid_frames: int = _MIN_SIDE_VALID_FRAMES,
) -> float | None:
    """Normalized left/right asymmetry, or None when only one leg moved.

    ``participation_rom_deg`` is the ROM a leg must reach to count as having
    performed the movement (pass the task's borderline ROM). This is what makes
    a unilateral clip abstain instead of always reporting maximal asymmetry.
    """
    left = sides.get("left")
    right = sides.get("right")
    if not (
        _participated(left, participation_rom_deg, min_valid_frames)
        and _participated(right, participation_rom_deg, min_valid_frames)
    ):
        return None
    return symmetry_index_score(left.rom_deg, right.rom_deg)
