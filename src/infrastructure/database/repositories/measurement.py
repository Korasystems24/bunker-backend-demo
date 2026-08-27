"""SqlMeasurementRepository: SQL тайм-серий измерений живёт только здесь."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.measurement import Measurement
from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.ports.measurement_repository import MeasurementRepository
from src.domain.value_objects.axis_zone import AxisZone
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.beam_reading import BeamReading
from src.domain.value_objects.buildup_snapshot import BuildupSnapshot
from src.domain.value_objects.save_stats import SaveStats
from src.domain.value_objects.series_point import SeriesPoint
from src.domain.value_objects.stats_snapshot import StatsSnapshot
from src.infrastructure.database.repositories.nodes import touch_node

# Порядок лучей в пакете фиксирован: 8 осей по 8 позиций ('A1'..'H8').
_AXIS_LETTERS = "ABCDEFGH"

# Округление на чтении: avg_level — 6 знаков, уровни/объём — 4, масса — 3
# (REAL-хранение добавляет шум float4).
_SELECT_MEASUREMENT_COLS = """
    id,
    event_id,
    ts,
    round(avg_level::numeric, 6)::double precision AS avg_level,
    round(min_level::numeric, 4)::double precision AS min_level,
    round(max_level::numeric, 4)::double precision AS max_level,
    round(volume::numeric, 4)::double precision    AS volume,
    round(mass::numeric, 3)::double precision      AS mass
"""

# Continuous aggregate: серия — часовые бакеты; overall min/max/avg —
# по сырым avg_level (min_avg_level / max_avg_level / sum/count).
_CAGG_STATS_SQL = """
WITH src AS (
    SELECT bucket,
           avg_level,
           min_level,
           max_level,
           mass,
           volume,
           min_avg_level,
           max_avg_level,
           sample_count,
           sum_avg_level
    FROM measurements_hourly
    WHERE bunker_id = :bunker_id AND bucket >= :frm
)
SELECT src.bucket AS ts,
       round(src.avg_level::numeric, 4)::double precision AS avg_level,
       round(src.min_level::numeric, 4)::double precision AS min_level,
       round(src.max_level::numeric, 4)::double precision AS max_level,
       round(src.mass::numeric, 3)::double precision      AS mass,
       round(src.volume::numeric, 4)::double precision    AS volume,
       (SELECT round(min(min_avg_level)::numeric, 4)::double precision FROM src) AS overall_min,
       (SELECT round(max(max_avg_level)::numeric, 4)::double precision FROM src) AS overall_max,
       (SELECT round(
            (sum(sum_avg_level) / nullif(sum(sample_count), 0))::numeric, 4
        )::double precision FROM src) AS overall_avg
FROM src
ORDER BY src.bucket
"""


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


def _measurement_from_row(row: Any) -> Measurement:
    m = row._mapping
    return Measurement(
        id=m["id"],
        event_id=m["event_id"],
        ts=m["ts"],
        avg_level=m["avg_level"],
        min_level=m["min_level"],
        max_level=m["max_level"],
        volume=m["volume"],
        mass=m["mass"],
    )


def _stats_from_rows(rows: Sequence[Any]) -> StatsSnapshot:
    series: list[SeriesPoint] = []
    overall_min: float | None = None
    overall_max: float | None = None
    overall_avg: float | None = None
    for row in rows:
        m = row._mapping
        overall_min = m["overall_min"]
        overall_max = m["overall_max"]
        overall_avg = m["overall_avg"]
        series.append(
            SeriesPoint(
                ts=m["ts"],
                avg_level=m["avg_level"],
                min_level=m["min_level"],
                max_level=m["max_level"],
                mass=m["mass"],
                volume=m["volume"],
            )
        )
    return StatsSnapshot(
        min_level=overall_min,
        max_level=overall_max,
        avg_level=overall_avg,
        series=series,
    )


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

    _INSERT_ZONES = text("""
        INSERT INTO buildup_zones
            (bunker_id, ts, axis, severity, score, deviation_m,
             affected_positions, algorithm_version)
        VALUES
            (:bunker_id, :ts, :axis, :severity, :score, :deviation_m,
             :affected_positions, :algorithm_version)
        ON CONFLICT DO NOTHING
    """)

    _LATEST_BUILDUP = text("""
        SELECT ts,
               algorithm_version,
               axis,
               severity,
               round(score::numeric, 3)::double precision AS score,
               round(deviation_m::numeric, 4)::double precision AS deviation_m,
               affected_positions
        FROM buildup_zones
        WHERE bunker_id = :bunker_id
          AND ts = (SELECT max(ts) FROM buildup_zones WHERE bunker_id = :bunker_id)
        ORDER BY axis
    """)

    _LATEST_MEASUREMENT = text(
        f"""
        SELECT {_SELECT_MEASUREMENT_COLS}
        FROM measurements
        WHERE bunker_id = :bunker_id
        ORDER BY ts DESC, event_id DESC
        LIMIT 1
        """
    )

    _LATEST_BEAMS = text("""
        SELECT beam_name,
               round(height::numeric, 4)::double precision AS height,
               beam_flags AS status
        FROM beam_readings
        WHERE bunker_id = :bunker_id AND ts = :ts
        ORDER BY beam_name
    """)

    _COUNT_RANGE_BASE = """
        SELECT count(*)
        FROM measurements
        WHERE bunker_id = :bunker_id
    """

    _RANGE_BASE = f"""
        SELECT {_SELECT_MEASUREMENT_COLS}
        FROM measurements
        WHERE bunker_id = :bunker_id
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save_batch(self, bunker_id: str, records: Sequence[TelemetryRecord]) -> SaveStats:
        inserted = 0
        beam_params: list[dict[str, Any]] = []
        zone_params: list[dict[str, Any]] = []

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
                    # Лучи и зоны пишем только для новых измерений: у дубля они уже есть.
                    beam_params.extend(
                        _beam_row(bunker_id, measurement.ts, beam_index, beam)
                        for beam_index, beam in enumerate(record.beams)
                    )
                    zone_params.extend(
                        {
                            "bunker_id": bunker_id,
                            "ts": measurement.ts,
                            "axis": zone.axis,
                            "severity": zone.severity,
                            "score": zone.score,
                            "deviation_m": zone.deviation_m,
                            "affected_positions": list(zone.affected_positions),
                            "algorithm_version": record.algorithm_version,
                        }
                        for zone in record.buildup_zones
                    )
            if beam_params:
                await session.execute(self._BULK_BEAMS, beam_params)
            if zone_params:
                await session.execute(self._INSERT_ZONES, zone_params)
            await touch_node(session, bunker_id)

        return SaveStats(
            received=len(records),
            inserted=inserted,
            duplicates=len(records) - inserted,
        )

    async def get_latest_with_beams(
        self, bunker_id: str
    ) -> tuple[Measurement, list[BeamReading]] | None:
        async with self._sessions() as session:
            params: dict[str, Any] = {"bunker_id": bunker_id}
            row = (await session.execute(self._LATEST_MEASUREMENT, params)).first()
            if row is None:
                return None
            measurement = _measurement_from_row(row)
            beam_rows = await session.execute(
                self._LATEST_BEAMS,
                {"bunker_id": bunker_id, "ts": measurement.ts},
            )
            beams = [
                BeamReading(beam_name=r.beam_name, height=r.height, status=r.status or "")
                for r in beam_rows
            ]
            return measurement, beams

    async def get_range(
        self,
        bunker_id: str,
        *,
        frm: datetime | None,
        to: datetime | None,
        limit: int,
        offset: int,
    ) -> list[Measurement]:
        sql, params = self._range_query(self._RANGE_BASE, bunker_id, frm, to)
        params.update(limit=limit, offset=offset)
        sql = f"{sql} ORDER BY ts DESC, event_id DESC LIMIT :limit OFFSET :offset"
        async with self._sessions() as session:
            rows = await session.execute(text(sql), params)
            return [_measurement_from_row(r) for r in rows]

    async def count_range(
        self, bunker_id: str, *, frm: datetime | None, to: datetime | None
    ) -> int:
        sql, params = self._range_query(self._COUNT_RANGE_BASE, bunker_id, frm, to)
        async with self._sessions() as session:
            result = await session.execute(text(sql), params)
            value = result.scalar_one()
            return int(value)

    def _range_query(
        self, base_sql: str, bunker_id: str, frm: datetime | None, to: datetime | None
    ) -> tuple[str, dict[str, Any]]:
        """from/to опциональны; сравнение включительное."""
        conditions: list[str] = []
        params: dict[str, Any] = {"bunker_id": bunker_id}
        if frm is not None:
            conditions.append("ts >= :frm")
            params["frm"] = frm
        if to is not None:
            conditions.append("ts <= :to")
            params["to"] = to
        suffix = f" AND {' AND '.join(conditions)}" if conditions else ""
        return base_sql + suffix, params

    async def get_stats(self, bunker_id: str, *, frm: datetime) -> StatsSnapshot | None:
        params: dict[str, Any] = {"bunker_id": bunker_id, "frm": frm}
        return await self._run_stats(_CAGG_STATS_SQL, params)

    async def get_latest_buildup(self, bunker_id: str) -> BuildupSnapshot | None:
        async with self._sessions() as session:
            rows = (await session.execute(self._LATEST_BUILDUP, {"bunker_id": bunker_id})).all()
            if not rows:
                return None
            first_row = rows[0]
            zones = tuple(
                AxisZone(
                    axis=r.axis,
                    severity=r.severity,
                    score=r.score,
                    deviation_m=r.deviation_m,
                    affected_positions=tuple(r.affected_positions or ()),
                )
                for r in rows
            )
            return BuildupSnapshot(
                ts=first_row.ts,
                algorithm_version=first_row.algorithm_version,
                zones=zones,
            )

    async def _run_stats(self, sql: str, params: dict[str, Any]) -> StatsSnapshot | None:
        async with self._sessions() as session:
            rows = (await session.execute(text(sql), params)).all()
            if not rows:
                return None
            return _stats_from_rows(rows)
