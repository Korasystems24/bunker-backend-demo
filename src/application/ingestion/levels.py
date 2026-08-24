"""Расчёт уровней по лучам: чистая функция, логика синхронна с моком."""

from collections.abc import Sequence

from src.domain.value_objects.beam import Beam


def compute_min_max_levels(beams: Sequence[Beam]) -> tuple[float | None, float | None]:
    """min/max по надёжным лучам: высота задана и статус-флагов нет вовсе.

    Любой флаг (NotUsed, Fault, WeakSignal, *Simulated, ...) исключает луч.
    Политика «какие флаги допустимы» уточняется позже настройками.
    """
    heights = [beam.height for beam in beams if beam.height is not None and not beam.status]
    if not heights:
        return None, None
    return min(heights), max(heights)
