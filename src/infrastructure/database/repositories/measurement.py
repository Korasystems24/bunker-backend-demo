"""SqlMeasurementRepository: SQL тайм-серий измерений живёт только здесь."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.ports.measurement_repository import MeasurementRepository
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.save_stats import SaveStats

# Порядок лучей в пакете фиксирован: 8 осей по 8 позиций ('A1'..'H8').
_AXIS_LETTERS = "ABCDEFGH"


def _beam_name(beam_index: int) -> str:
    """Имя луча из его позиции в пакете: 0 -> 'A1', 63 -> 'H8'."""
    return f"{_AXIS_LETTERS[beam_index // 8]}{beam_index % 8 + 1}"


def _beam_row(bunker_id: str, ts: datetime, beam_index: int, beam: Beam) -> dict[str, Any]:
    return {
        "bunker_id": bunker_id,
        "ts": ts,
        "beam_name": _beam_name(beam_index),
        "height": beam.height,
        "raw_status": beam.raw_status,
        "beam_flags": ", ".join(status.value for status in beam.status),
    }


class SqlMeasurementRepository(MeasurementRepository):
    _INSERT_MEASUREMENT = text("""
        INSERT INTO measurements
            (bunker_id, event_id, ts, avg_level, min_level, max_level, volume, mass)
        VALUES
            (:bunker_id, :event_id, :ts, :avg_level, :min_level, :max_level,
             :volume, :mass)
        ON CONFLICT DO NOTHING
        RETURNING event_id
    """)

    _BULK_BEAMS = text("""
        INSERT INTO beam_readings (bunker_id, ts, beam_name, height, raw_status, beam_flags)
        VALUES (:bunker_id, :ts, :beam_name, :height, :raw_status, :beam_flags)
        ON CONFLICT DO NOTHING
    """)

    _TOUCH_NODE = text("UPDATE edge_nodes SET last_seen_at = now() WHERE bunker_id = :bunker_id")

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save_batch(self, bunker_id: str, records: Sequence[TelemetryRecord]) -> SaveStats:
        inserted = 0
        beam_params: list[dict[str, Any]] = []

        async with self._sessions() as session, session.begin():
            for record in records:
                measurement = record.measurement
                result = await session.execute(
                    self._INSERT_MEASUREMENT,
                    {
                        "bunker_id": bunker_id,
                        "event_id": str(measurement.event_id),
                        "ts": measurement.ts,
                        "avg_level": measurement.avg_level,
                        "min_level": measurement.min_level,
                        "max_level": measurement.max_level,
                        "volume": measurement.volume,
                        "mass": measurement.mass,
                    },
                )
                if result.scalar() is not None:
                    inserted += 1
                    # Лучи пишем только для новых измерений: у дубля они уже есть.
                    beam_params.extend(
                        _beam_row(bunker_id, measurement.ts, beam_index, beam)
                        for beam_index, beam in enumerate(record.beams)
                    )
            if beam_params:
                await session.execute(self._BULK_BEAMS, beam_params)
            await self._touch_node(session, bunker_id)

        return SaveStats(
            received=len(records),
            inserted=inserted,
            duplicates=len(records) - inserted,
        )

    async def _touch_node(self, session: AsyncSession, bunker_id: str) -> None:
        # Касание телеметрии продлевает жизнь узлу (dead-man switch, шаг 4).
        # Строки может не быть до первого POST /health — тогда no-op.
        await session.execute(self._TOUCH_NODE, {"bunker_id": bunker_id})
