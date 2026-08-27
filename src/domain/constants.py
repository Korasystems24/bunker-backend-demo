"""Константы домена."""

from typing import Final

# Число лучей радара в одном пакете телеметрии ('A1'..'H8').
BEAM_COUNT: Final = 64

# EdgePC отдаёт avg_level и высоты лучей в миллиметрах; Query API и фронт — в метрах.
MM_PER_M: Final = 1000.0
