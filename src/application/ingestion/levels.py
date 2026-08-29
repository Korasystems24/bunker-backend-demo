"""Расчёт уровней по лучам: чистая функция по достоверным лучам."""

from collections.abc import Sequence

from src.domain.beam_rules import is_hard_unreliable
from src.domain.value_objects.beam import Beam


def sanitize_avg_level(avg_level: float | None) -> float | None:
    """Ноль от радара — сбой (нет эха), не пустой бункер."""
    if avg_level is None or avg_level <= 0:
        return None
    return avg_level


def compute_min_max_levels(beams: Sequence[Beam]) -> tuple[float | None, float | None]:
    """Min/max по лучам без жёстко ненадёжных статусов и с положительной высотой."""
    heights = [
        beam.height
        for beam in beams
        if beam.height is not None
        and beam.height > 0
        and not is_hard_unreliable(beam.status)
    ]
    if not heights:
        return None, None
    return min(heights), max(heights)
