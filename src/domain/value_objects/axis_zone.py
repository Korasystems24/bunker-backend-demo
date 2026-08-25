"""Value object: результат buildup-детектора для одной оси."""

from typing import Literal

import pydantic

Severity = Literal["none", "low", "medium", "high"]

# Фронт получает severity/score как непрозрачные значения бэкенда
# (пороги не пересчитывает и не хардкодит).
class AxisZone(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    axis: str
    severity: Severity
    score: float
    deviation_m: float
    affected_positions: tuple[int, ...] = ()
