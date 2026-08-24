"""DTO приёма данных от edge (контракт фазы 7а; модели переиспользуют домен)."""

import pydantic

from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.telemetry_packet import TelemetryPacket


class TelemetryRequest(pydantic.BaseModel):
    bunker_id: str
    node_id: str | None = None
    packets: list[TelemetryPacket] = pydantic.Field(min_length=1)


# Список событий переиспользует доменную EdgeEvent как есть.
class EventsRequest(pydantic.BaseModel):
    bunker_id: str
    node_id: str | None = None
    events: list[EdgeEvent] = pydantic.Field(min_length=1)


class HealthRequest(HealthSnapshot):
    """Тело POST /health совпадает со снимком узла."""


class IngestAccepted(pydantic.BaseModel):
    received: int
    inserted: int
    duplicates: int


class HealthAccepted(pydantic.BaseModel):
    status: str = "ok"
