"""DTO приёма данных от edge (контракт фазы 7а; модели переиспользуют домен)."""

import pydantic

from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.telemetry_packet import TelemetryPacket


class TelemetryRequest(pydantic.BaseModel):
    """Пакеты как шлёт EdgePC: avg_level и Beam.height — миллиметры."""

    bunker_id: str
    packets: list[TelemetryPacket] = pydantic.Field(min_length=1)


# Список событий переиспользует доменную EdgeEvent как есть.
class EventsRequest(pydantic.BaseModel):
    bunker_id: str
    events: list[EdgeEvent] = pydantic.Field(min_length=1)


class HealthRequest(HealthSnapshot):
    """Тело POST /health: снимок узла + bunker_id рядом с ним.

    EdgePC не шлёт node_id — идентичность узла выводится из bunker_id
    ('edge-<суффикс>', см. infrastructure.database.repositories.nodes).
    """

    bunker_id: str


class IngestAccepted(pydantic.BaseModel):
    received: int
    inserted: int
    duplicates: int


class HealthAccepted(pydantic.BaseModel):
    status: str = "ok"
