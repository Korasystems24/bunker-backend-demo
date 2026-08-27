"""Агрегат записи: измерение вместе со своими лучами."""

from dataclasses import dataclass

from src.domain.entities.measurement import Measurement
from src.domain.value_objects.axis_zone import AxisZone
from src.domain.value_objects.beam import Beam


@dataclass(frozen=True, slots=True)
class TelemetryRecord:
    measurement: Measurement
    beams: list[Beam]
    buildup_zones: tuple[AxisZone, ...] = ()
    algorithm_version: str = "radial-slope-v1"
