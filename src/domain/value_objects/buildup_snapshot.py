"""Снимок зон налипания: результат compute-on-write, чтение GET /buildup."""

import pydantic

from src.domain.value_objects.axis_zone import AxisZone
from src.domain.value_objects.types import Timestamp


class BuildupSnapshot(pydantic.BaseModel):
    """ts совпадает с измерением, по которому считали зоны при ингесте."""

    model_config = pydantic.ConfigDict(frozen=True)

    ts: Timestamp
    algorithm_version: str
    zones: tuple[AxisZone, ...]
