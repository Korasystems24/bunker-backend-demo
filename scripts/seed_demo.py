"""Сидинг демо-истории: генератор из мока → TimescaleDB через COPY.

Прямой порт логики mock-server (buildGeometry / generateBeams / дрейф уровня /
налипание на оси) на 30 дней × 2 бункера. Запуск:

    uv run python scripts/seed_demo.py                 # 30 дней, шаг 15 минут
    uv run python scripts/seed_demo.py --reset         # с очисткой тайм-серий
    uv run python scripts/seed_demo.py --days 90 --interval-minutes 5

Отличие от ингеста (осознанное): сид воспроизводит правило мока — из avg/min/max
исключаются только «жёстко ненадёжные» лучи (Disabled/DistanceNotUpdating/
NotUsed/Unknown); политика флагов уточняется вместе с заказчиком.
"""

import argparse
import asyncio
import json
import math
import random
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

import asyncpg
from src.config.settings import get_settings
from src.infrastructure.database.repositories.nodes import node_id_for_bunker

# ── Константы геометрии и физики (1:1 с моком) ────────────────────────────────

AXES: Final = ("A", "B", "C", "D", "E", "F", "G", "H")
POSITIONS: Final = tuple(range(1, 9))
AXIS_AZIMUTHS_DEG: Final[dict[str, int]] = {
    "A": 0, "B": 45, "C": 90, "D": 135, "E": 180, "F": 225, "G": 270, "H": 315,
}
RADIUS_FRACTIONS: Final[tuple[float, ...]] = (0.1, 0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.95)
BUNKER_RADIUS_M: Final = 3.5
BUNKER_HEIGHT_M: Final = 8.0
SENSOR_Z: Final = BUNKER_HEIGHT_M + 0.5
DENSITY_T_PER_M3: Final = 2.3
VOLUME_FACTOR_M3_PER_LEVEL: Final = 5.3

KNOWN_FLAGS: Final = (
    "Unknown",
    "NotUsed",
    "Disabled",
    "DistanceNotUpdating",
    "WeakSignal",
    "TooShort",
    "TooLong",
    "OutOfReposeAngle",
)
# Луч с любым из этих флагов не участвует в avg/min/max (правило мока).
HARD_UNRELIABLE_FLAGS: Final = frozenset({"Disabled", "DistanceNotUpdating", "NotUsed", "Unknown"})

BUNKERS: Final = (
    {
        "id": "bunker-1",
        "name": "Бункер №1",
        "base_level": 3.2,
        "drift_dir": 1,
        "buildup_axis": "C",
        "buildup_level": 0.0,
    },
    {
        "id": "bunker-2",
        "name": "Бункер №2",
        "base_level": 5.1,
        "drift_dir": -1,
        "buildup_axis": "F",
        "buildup_level": 0.4,
    },
)


@dataclass(slots=True)
class BunkerState:
    bunker_id: str
    base_level: float
    drift_dir: int
    buildup_axis: str
    buildup_level: float


def build_geometry(bunker_id: str) -> dict:
    """Порт buildGeometry мока: расчёт — обязанность конфигуратора/сида."""
    beams = []
    for axis in AXES:
        azimuth_rad = math.radians(AXIS_AZIMUTHS_DEG[axis])
        for pos in POSITIONS:
            r = BUNKER_RADIUS_M * RADIUS_FRACTIONS[pos - 1]
            beams.append(
                {
                    "beam_name": f"{axis}{pos}",
                    "axis": axis,
                    "position": pos,
                    "x": round(r * math.cos(azimuth_rad), 4),
                    "y": round(r * math.sin(azimuth_rad), 4),
                    "z": 0,
                }
            )
    return {
        "bunker_id": bunker_id,
        "shape": {
            "type": "truncated_cone",
            "top_diameter_m": round(BUNKER_RADIUS_M * 2, 4),
            "bottom_diameter_m": round(BUNKER_RADIUS_M * 1.2, 4),
            "height_m": BUNKER_HEIGHT_M,
        },
        "sensor": {"x": 0, "y": 0, "z": SENSOR_Z, "tilt_deg": 0},
        "beams": beams,
    }


def pick_status(rng: random.Random, position: int) -> str:
    """Внешние позиции деградируют чаще; 1–3 флага из пула, как в моке."""
    degrade_chance = 0.30 if position >= 6 else 0.08
    if rng.random() < degrade_chance:
        count = 1 if rng.random() < 0.6 else 2 if rng.random() < 0.7 else 3
        pool = list(KNOWN_FLAGS)
        flags = [pool.pop(rng.randrange(len(pool))) for _ in range(count)]
        return ", ".join(flags)
    return ""


def is_hard_unreliable(status: str) -> bool:
    """Луч не участвует в avg/min/max при «жёстких» флагах (правило мока)."""
    flags = {f.strip() for f in status.split(",")} if status else set()
    return bool(flags & HARD_UNRELIABLE_FLAGS)


def generate_beams(state: BunkerState, rng: random.Random) -> list[tuple[str, float, str]]:
    beams: list[tuple[str, float, str]] = []
    for axis in AXES:
        azimuth_var = math.sin(math.radians(AXIS_AZIMUTHS_DEG[axis]) * 2) * 0.6
        for pos in POSITIONS:
            status = pick_status(rng, pos)
            flags = {f.strip() for f in status.split(",")} if status else set()
            if flags & HARD_UNRELIABLE_FLAGS:
                # Ненадёжный луч хранится с высотой 0 и строкой флагов (как в моке).
                beams.append((f"{axis}{pos}", 0.0, status))
                continue
            radial_drop = (pos - 1) * 0.20
            noise = (rng.random() - 0.5) * 0.35
            bump = (
                state.buildup_level * ((pos - 5) / 3)
                if axis == state.buildup_axis and pos >= 6
                else 0.0
            )
            height = max(0.1, state.base_level - radial_drop + azimuth_var + noise + bump)
            beams.append((f"{axis}{pos}", round(height, 4), ""))
    return beams


def generate_measurement(
    state: BunkerState, rng: random.Random, ts: datetime
) -> tuple[tuple, list[tuple]]:
    """Один тик телеметрии: строка measurements + 64 строки beam_readings.

    Дрейф базового уровня и рост налипания — до расчёта лучей, как в моке.
    """
    state.base_level += state.drift_dir * (rng.random() * 0.03)
    if state.base_level > 6.5:
        state.drift_dir = -1
    if state.base_level < 1.0:
        state.drift_dir = 1

    state.buildup_level = min(1.4, state.buildup_level + rng.random() * 0.01)
    if rng.random() < 0.002:
        state.buildup_level = 0.0

    beams = generate_beams(state, rng)
    reliable = [h for _, h, s in beams if h > 0 and not is_hard_unreliable(s)]

    if reliable:
        avg_level = round(sum(reliable) / len(reliable), 6)
        min_level = round(min(reliable), 4)
        max_level = round(max(reliable), 4)
    else:
        avg_level = min_level = max_level = None  # тип: ignore[assignment]

    volume = round(avg_level * VOLUME_FACTOR_M3_PER_LEVEL, 4) if avg_level is not None else None
    mass = (
        round(avg_level * VOLUME_FACTOR_M3_PER_LEVEL * DENSITY_T_PER_M3, 3)
        if avg_level is not None
        else None
    )

    measurement_row = (
        state.bunker_id, uuid.uuid4(), ts, avg_level, min_level, max_level, volume, mass
    )
    beam_rows = [
        (state.bunker_id, ts, name, height, None, status)
        for name, height, status in beams
    ]
    return measurement_row, beam_rows


def generate_history(
    state: BunkerState, rng: random.Random, *, days: int, interval_minutes: int
) -> tuple[list[tuple], list[tuple]]:
    """Равномерная сетка ts, старые вперёд; последнее измерение — «сейчас»."""
    count = days * 24 * 60 // interval_minutes
    end = datetime.now(UTC)
    start = end - timedelta(minutes=count * interval_minutes)
    measurements: list[tuple] = []
    beam_rows: list[tuple] = []
    for i in range(count + 1):
        ts = start + timedelta(minutes=i * interval_minutes)
        m_row, b_rows = generate_measurement(state, rng, ts)
        measurements.append(m_row)
        beam_rows.extend(b_rows)
    return measurements, beam_rows


async def seed_reference_data(conn: asyncpg.Connection) -> None:
    """bunkers/geometries заливаются сидом (админка конфигуратора — после демо)."""
    for spec in BUNKERS:
        await conn.execute(
            """
            INSERT INTO bunkers (id, name) VALUES ($1, $2)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """,
            spec["id"],
            spec["name"],
        )
        geometry = build_geometry(spec["id"])
        await conn.execute(
            """
            INSERT INTO geometries (bunker_id, shape, sensor, beams, updated_at)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, now())
            ON CONFLICT (bunker_id) DO UPDATE SET
                shape = EXCLUDED.shape,
                sensor = EXCLUDED.sensor,
                beams = EXCLUDED.beams,
                updated_at = now()
            """,
            spec["id"],
            json.dumps(geometry["shape"]),
            json.dumps(geometry["sensor"]),
            json.dumps(geometry["beams"]),
        )
        # Узел online сразу после сида: /bunkers и /api/v1/health живые для демо.
        await conn.execute(
            """
            INSERT INTO edge_nodes
                (node_id, bunker_id, last_seen_at, cpu, ram, disk, edge_time, status)
            VALUES ($1, $2, now(), $3, $4, $5, now(), 'online')
            ON CONFLICT (node_id) DO UPDATE SET
                last_seen_at = now(),
                cpu = EXCLUDED.cpu,
                ram = EXCLUDED.ram,
                disk = EXCLUDED.disk,
                edge_time = now(),
                status = 'online'
            """,
            # Тот же вывод node_id из bunker_id, что и в ингест-пути.
            node_id_for_bunker(spec["id"]),
            spec["id"],
            round(random.uniform(20, 60), 1),
            round(random.uniform(40, 70), 1),
            round(random.uniform(55, 65), 1),
        )


async def copy_series(
    conn: asyncpg.Connection,
    measurements: list[tuple],
    beam_rows: list[tuple],
) -> None:
    # COPY (binary) вместо INSERT'ов: минуты на миллионы строк → секунды.
    await conn.copy_records_to_table(
        "measurements",
        columns=(
            "bunker_id", "event_id", "ts",
            "avg_level", "min_level", "max_level", "volume", "mass",
        ),
        records=measurements,
    )
    await conn.copy_records_to_table(
        "beam_readings",
        columns=("bunker_id", "ts", "beam_name", "height", "raw_status", "beam_flags"),
        records=beam_rows,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Сид демо-истории бункеров")
    parser.add_argument("--days", type=int, default=30, help="глубина истории в днях")
    parser.add_argument("--interval-minutes", type=int, default=15, help="шаг между измерениями")
    parser.add_argument("--seed", type=int, default=42, help="зерно RNG (воспроизводимость)")
    parser.add_argument("--reset", action="store_true", help="очистить тайм-серии перед сидом")
    args = parser.parse_args()

    started = time.monotonic()
    dsn = get_settings().database.url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        if args.reset:
            await conn.execute("TRUNCATE measurements, beam_readings, buildup_zones")

        await seed_reference_data(conn)

        total_measurements = 0
        total_beams = 0
        for index, spec in enumerate(BUNKERS):
            state = BunkerState(
                bunker_id=spec["id"],
                base_level=spec["base_level"],
                drift_dir=spec["drift_dir"],
                buildup_axis=spec["buildup_axis"],
                buildup_level=spec["buildup_level"],
            )
            rng = random.Random(args.seed + index)
            measurements, beam_rows = generate_history(
                state, rng, days=args.days, interval_minutes=args.interval_minutes
            )
            await copy_series(conn, measurements, beam_rows)
            total_measurements += len(measurements)
            total_beams += len(beam_rows)
            print(f"[seed] {spec['id']}: {len(measurements)} измерений, {len(beam_rows)} лучей")
    finally:
        await conn.close()

    elapsed = time.monotonic() - started
    print(f"[seed] всего: {total_measurements} измерений, {total_beams} лучей за {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
