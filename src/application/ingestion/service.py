"""IngestionService: валидация сделана схемами API, здесь — правила и запись."""

from collections.abc import Sequence

from src.application.ingestion.levels import compute_min_max_levels
from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.measurement import Measurement
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.ports.event_repository import EventRepository
from src.domain.ports.health_repository import HealthRepository
from src.domain.ports.measurement_repository import MeasurementRepository
from src.domain.value_objects.save_stats import SaveStats


class IngestionService:
    def __init__(
        self,
        measurements: MeasurementRepository,
        events: EventRepository,
        health: HealthRepository,
    ) -> None:
        self._measurements = measurements
        self._events = events
        self._health = health

    async def ingest_telemetry(
        self, bunker_id: str, packets: Sequence[TelemetryPacket]
    ) -> SaveStats:
        records: list[TelemetryRecord] = []
        for packet in packets:
            min_level, max_level = compute_min_max_levels(packet.beams)
            measurement = Measurement(
                event_id=packet.event_id,
                ts=packet.ts,
                avg_level=packet.avg_level,
                min_level=min_level,
                max_level=max_level,
                volume=packet.volume,
                mass=packet.mass,
            )
            records.append(TelemetryRecord(measurement=measurement, beams=list(packet.beams)))
        return await self._measurements.save_batch(bunker_id, records)

    async def ingest_events(self, bunker_id: str, events: Sequence[EdgeEvent]) -> SaveStats:
        return await self._events.save_batch(bunker_id, events)

    async def ingest_health(self, bunker_id: str, snapshot: HealthSnapshot) -> None:
        await self._health.upsert(snapshot, bunker_id=bunker_id)
