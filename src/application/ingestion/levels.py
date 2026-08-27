"""Расчёт уровней по лучам: чистая функция по достоверным лучам."""

from collections.abc import Sequence

from src.domain.beam_rules import is_hard_unreliable
from src.domain.value_objects.beam import Beam


def compute_min_max_levels(beams: Sequence[Beam]) -> tuple[float | None, float | None]:
    """Min/max по лучам без жёстко ненадёжных статусов и с известной высотой."""
    heights = [
        beam.height
        for beam in beams
        if beam.height is not None and not is_hard_unreliable(beam.status)
    ]
    if not heights:
        return None, None
    return min(heights), max(heights)
