"""Порт buildup-детектора: Strategy — критерий ещё согласовывается с заказчиком."""

from collections.abc import Sequence
from typing import Protocol

from src.domain.value_objects.axis_zone import AxisZone
from src.domain.value_objects.beam import Beam


class BuildupDetector(Protocol):
    algorithm_version: str

    def detect(self, beams: Sequence[Beam]) -> list[AxisZone]:
        """Зоны налипания по лучам одного измерения (по зоне на каждую ось A..H)."""
        ...
