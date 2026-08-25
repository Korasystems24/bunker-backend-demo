"""Константы домена."""

from typing import Final

# Число лучей радара в одном пакете телеметрии ('A1'..'H8').
BEAM_COUNT: Final = 64

# «Жёстко ненадёжные» статусы: луч с любым из них исключается из расчётов
# уровней (avg/min/max) и buildup-эвристики — правило мока (isBeamReliable /
# computeBuildupZones). Остальные флаги (WeakSignal, *Simulated, ...) луч
# не исключают. Строки совпадают со значениями BeamStatus.
HARD_UNRELIABLE_BEAM_FLAGS: Final[frozenset[str]] = frozenset(
    {"Disabled", "DistanceNotUpdating", "NotUsed", "Unknown"}
)
