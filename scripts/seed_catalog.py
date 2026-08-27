"""Загрузка версионируемого JSON-каталога бункеров и геометрии."""

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg
from src.config.settings import get_settings
from src.infrastructure.catalog import JsonCatalogProvider


async def seed_catalog(
    conn: asyncpg.Connection,
    provider: JsonCatalogProvider,
    *,
    replace_geometry: bool = False,
) -> None:
    geometry_conflict = (
        """
        ON CONFLICT (bunker_id) DO UPDATE SET
            shape = EXCLUDED.shape,
            sensor = EXCLUDED.sensor,
            beams = EXCLUDED.beams,
            updated_at = now()
        """
        if replace_geometry
        else "ON CONFLICT (bunker_id) DO NOTHING"
    )
    async with conn.transaction():
        for bunker in provider.catalog.bunkers:
            await conn.execute(
                """
                INSERT INTO bunkers (id, name) VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """,
                bunker.id,
                bunker.name,
            )
            geometry = provider.geometry_for(bunker.id)
            await conn.execute(
                f"""
            INSERT INTO geometries (bunker_id, shape, sensor, beams, updated_at)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, now())
            {geometry_conflict}
            """,
                bunker.id,
                geometry.shape.model_dump_json(),
                geometry.sensor.model_dump_json(),
                json.dumps(
                    [beam.model_dump(mode="json") for beam in geometry.beams],
                    ensure_ascii=False,
                ),
            )
            print(f"[catalog] {bunker.id}: {bunker.name}")


async def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Загрузить JSON-каталог бункеров")
    parser.add_argument("--catalog", type=Path, default=settings.catalog.path)
    parser.add_argument(
        "--replace-geometry",
        action="store_true",
        help="явно перезаписать существующую геометрию",
    )
    args = parser.parse_args()
    provider = JsonCatalogProvider(args.catalog)
    dsn = settings.database.url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await seed_catalog(conn, provider, replace_geometry=args.replace_geometry)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
