"""Справочник бункеров и геометрии (каталог, не телеметрия).

Историю измерений не генерирует: её пишет EdgePC через Ingestion API.
"""

import argparse
import asyncio
import json
import math
from typing import Final

import asyncpg
from src.config.settings import get_settings

AXES: Final = ("A", "B", "C", "D", "E", "F", "G", "H")
POSITIONS: Final = tuple(range(1, 9))
AXIS_AZIMUTHS_DEG: Final[dict[str, int]] = {
    "A": 0, "B": 45, "C": 90, "D": 135, "E": 180, "F": 225, "G": 270, "H": 315,
}
RADIUS_FRACTIONS: Final[tuple[float, ...]] = (0.1, 0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.95)
BUNKER_RADIUS_M: Final = 3.5
BUNKER_HEIGHT_M: Final = 8.0
SENSOR_Z: Final = BUNKER_HEIGHT_M + 0.5

BUNKERS: Final = (
    {"id": "bunker-1", "name": "Бункер №1"},
    {"id": "bunker-2", "name": "Бункер №2"},
)


def build_geometry(bunker_id: str) -> dict:
    beams = []
    for axis in AXES:
        azimuth_rad = math.radians(AXIS_AZIMUTHS_DEG[axis])
        for pos in POSITIONS:
            radius = BUNKER_RADIUS_M * RADIUS_FRACTIONS[pos - 1]
            beams.append(
                {
                    "beam_name": f"{axis}{pos}",
                    "axis": axis,
                    "position": pos,
                    "x": round(radius * math.cos(azimuth_rad), 4),
                    "y": round(radius * math.sin(azimuth_rad), 4),
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


async def seed_catalog(conn: asyncpg.Connection) -> None:
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
        print(f"[catalog] {spec['id']}: {spec['name']}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Залить справочник бункеров и геометрии")
    parser.parse_args()
    dsn = get_settings().database.url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await seed_catalog(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
