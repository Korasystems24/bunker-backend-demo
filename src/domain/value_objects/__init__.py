"""Value objects домена."""

from src.domain.value_objects.beam import Beam
from src.domain.value_objects.beam_status import BeamStatus
from src.domain.value_objects.save_stats import SaveStats
from src.domain.value_objects.types import (
    EdgeEventPayload,
    EventType,
    Measurement,
    TelemetryBeams,
    Timestamp,
)

__all__ = [
    "Beam",
    "BeamStatus",
    "EdgeEventPayload",
    "EventType",
    "Measurement",
    "SaveStats",
    "TelemetryBeams",
    "Timestamp",
]
