"""Расчёт уровней по лучам: чистая функция, логика синхронна с моком."""

from collections.abc import Sequence

from src.domain.constants import HARD_UNRELIABLE_BEAM_FLAGS
from src.domain.value_objects.beam import Beam


def compute_min_max_levels(beams: Sequence[Beam]) -> tuple[float | None, float | None]:
    """min/max по достоверным лучам — правило мока (isBeamReliable): луч
    исключается только при «жёстком» флаге (Disabled, DistanceNotUpdating,
    NotUsed, Unknown) или отсутствии высоты. Мягкие флаги (WeakSignal,
    *Simulated, ...) луч не исключают."""
    heights = [
        beam.height
        for beam in beams
        if beam.height is not None
        and not {status.value for status in beam.status} & HARD_UNRELIABLE_BEAM_FLAGS
    ]
    if not heights:
        return None, None
    return min(heights), max(heights)
