"""Сущности домена."""

from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.measurement import Measurement
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.entities.telemetry_record import TelemetryRecord

__all__ = [
    "EdgeEvent",
    "HealthSnapshot",
    "Measurement",
    "TelemetryPacket",
    "TelemetryRecord",
]
