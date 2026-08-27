"""Перевод единиц EdgePC → домен/Query API.

Радар шлёт уровни и высоты лучей в миллиметрах. Контракт фронта — метры.
Масса и объём приходят уже в т / м³ и не трогаются.
"""

from src.domain.constants import MM_PER_M


def mm_to_m(value_mm: float | None) -> float | None:
    if value_mm is None:
        return None
    return value_mm / MM_PER_M
