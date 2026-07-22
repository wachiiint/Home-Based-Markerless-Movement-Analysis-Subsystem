"""Print-verify: correct for printer scaling.

The patient prints the board at 100%, then measures a nominal 100 mm reference
bar with a ruler and enters the value. ``print_scale_factor`` corrects every
downstream metric length; without it a mis-scaled print silently biases scale.
"""

NOMINAL_BAR_MM = 100.0
# If the measured bar deviates more than this, the print is almost certainly
# wrong (fit-to-page) rather than normal printer tolerance -> reject.
MAX_DEVIATION_RATIO = 0.10


def compute_print_scale(measured_bar_mm: float, nominal_bar_mm: float = NOMINAL_BAR_MM) -> tuple[float, list[str]]:
    """Return (print_scale_factor, warnings).

    ``effective_length = nominal_length * print_scale_factor``, where the factor
    is ``measured / nominal``. The measured bar *is* the printed reality: if the
    printer enlarged the board (measured 110 mm vs nominal 100 mm) every square is
    10% bigger on paper, so the effective length must scale UP by 1.1. Using the
    reciprocal biases the recovered metric scale in the wrong direction.
    """
    warnings: list[str] = []
    if measured_bar_mm <= 0:
        raise ValueError("measured bar length must be positive")
    factor = measured_bar_mm / nominal_bar_mm
    deviation = abs(measured_bar_mm - nominal_bar_mm) / nominal_bar_mm
    if deviation > MAX_DEVIATION_RATIO:
        warnings.append(
            f"measured bar {measured_bar_mm}mm deviates {deviation:.0%} from "
            f"{nominal_bar_mm}mm; check that the board was printed at 100% (no fit-to-page)"
        )
    return factor, warnings
