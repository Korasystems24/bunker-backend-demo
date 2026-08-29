"""IngestionService: валидация сделана схемами API, здесь — правила и запись."""

from collections.abc import Sequence
from datetime import UTC, datetime

import loguru

from src.application.ingestion.levels import compute_min_max_levels, sanitize_avg_level
from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.measurement import Measurement
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.ports.buildup_detector import BuildupDetector
from src.domain.ports.ingestion_uow import IngestionUnitOfWork
from src.domain.value_objects.save_stats import SaveStats


class IngestionService:
    def __init__(
        self,
        uow: IngestionUnitOfWork,
        buildup: BuildupDetector,
        *,
        clock_drift_warn_sec: int,
    ) -> None:
        self._uow = uow
        self._buildup = buildup
        self._clock_drift_warn_sec = clock_drift_warn_sec

    async def ingest_telemetry(
        self, bunker_id: str, packets: Sequence[TelemetryPacket]
    ) -> SaveStats:
        async with self._uow.transaction(bunker_id) as transaction:
            accepted_ids = await transaction.reserve_telemetry(
                [packet.event_id for packet in packets]
            )
            records: list[TelemetryRecord] = []
            remaining_ids = accepted_ids.copy()
            for packet in packets:
                if packet.event_id not in remaining_ids:
                    continue
                remaining_ids.remove(packet.event_id)
                min_level, max_level = compute_min_max_levels(packet.beams)
                measurement = Measurement(
                    event_id=packet.event_id,
                    ts=packet.ts,
                    avg_level=sanitize_avg_level(packet.avg_level),
                    min_level=min_level,
                    max_level=max_level,
                    volume=packet.volume,
                    mass=packet.mass,
                )
                zones = self._buildup.detect(packet.beams)
                records.append(
                    TelemetryRecord(
                        measurement=measurement,
                        beams=list(packet.beams),
                        buildup_zones=tuple(zones),
                        algorithm_version=self._buildup.algorithm_version,
                    )
                )
            await transaction.save_telemetry(records)
        inserted = len(records)
        return SaveStats(
            received=len(packets),
            inserted=inserted,
            duplicates=len(packets) - inserted,
        )

    async def ingest_events(self, bunker_id: str, events: Sequence[EdgeEvent]) -> SaveStats:
        async with self._uow.transaction(bunker_id) as transaction:
            inserted = await transaction.save_events(events)
        return SaveStats(
            received=len(events),
            inserted=inserted,
            duplicates=len(events) - inserted,
        )

    async def ingest_health(self, bunker_id: str, snapshot: HealthSnapshot) -> None:
        drift_seconds = abs((datetime.now(UTC) - snapshot.ts).total_seconds())
        if drift_seconds > self._clock_drift_warn_sec:
            loguru.logger.warning(
                "Edge clock drift: bunker_id={}, drift_seconds={:.1f}",
                bunker_id,
                drift_seconds,
            )
        async with self._uow.transaction(bunker_id) as transaction:
            await transaction.save_health(snapshot)
