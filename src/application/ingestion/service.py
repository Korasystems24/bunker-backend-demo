"""IngestionService: валидация сделана схемами API, здесь — правила и запись."""

from collections.abc import Sequence

from src.application.ingestion.levels import compute_min_max_levels
from src.application.ingestion.units import packet_to_meters
from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.measurement import Measurement
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.exceptions import UnknownBunkerError
from src.domain.ports.buildup_detector import BuildupDetector
from src.domain.ports.bunker_repository import BunkerRepository
from src.domain.ports.event_repository import EventRepository
from src.domain.ports.health_repository import HealthRepository
from src.domain.ports.measurement_repository import MeasurementRepository
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.beam_reading import BeamReading
from src.domain.value_objects.save_stats import SaveStats

_AXIS_LETTERS = "ABCDEFGH"


def _beam_name(beam_index: int) -> str:
    return f"{_AXIS_LETTERS[beam_index // 8]}{beam_index % 8 + 1}"


def _to_readings(beams: Sequence[Beam]) -> list[BeamReading]:
    """Имя луча из позиции в пакете — то же правило, что при записи beam_readings."""
    return [
        BeamReading(
            beam_name=_beam_name(index),
            height=beam.height,
            status=", ".join(status.value for status in beam.status),
        )
        for index, beam in enumerate(beams)
    ]


class IngestionService:
    def __init__(
        self,
        measurements: MeasurementRepository,
        events: EventRepository,
        health: HealthRepository,
        bunkers: BunkerRepository,
        buildup: BuildupDetector,
    ) -> None:
        self._measurements = measurements
        self._events = events
        self._health = health
        self._bunkers = bunkers
        self._buildup = buildup

    async def ingest_telemetry(
        self, bunker_id: str, packets: Sequence[TelemetryPacket]
    ) -> SaveStats:
        await self._ensure_known(bunker_id)
        records: list[TelemetryRecord] = []
        for packet in packets:
            packet = packet_to_meters(packet)
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
            zones = self._buildup.detect(_to_readings(packet.beams))
            records.append(
                TelemetryRecord(
                    measurement=measurement,
                    beams=list(packet.beams),
                    buildup_zones=tuple(zones),
                    algorithm_version=self._buildup.algorithm_version,
                )
            )
        return await self._measurements.save_batch(bunker_id, records)

    async def ingest_events(self, bunker_id: str, events: Sequence[EdgeEvent]) -> SaveStats:
        await self._ensure_known(bunker_id)
        return await self._events.save_batch(bunker_id, events)

    async def ingest_health(self, bunker_id: str, snapshot: HealthSnapshot) -> None:
        await self._ensure_known(bunker_id)
        await self._health.upsert(snapshot, bunker_id=bunker_id)

    async def _ensure_known(self, bunker_id: str) -> None:
        if not await self._bunkers.exists(bunker_id):
            raise UnknownBunkerError()
