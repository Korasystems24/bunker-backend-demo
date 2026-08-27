"""SqlBunkerRepository: справочник бункеров + геометрия.

Справочные таблицы — мир ORM; join со свежестью edge_nodes делается raw SQL,
поскольку edge_nodes не имеет ORM-модели (телеметрия — raw-SQL мир).
online в выдаче — по last_seen_at; status/alerts ведёт SilenceMonitor.
"""

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.bunker import Bunker
from src.domain.entities.geometry import Geometry
from src.domain.ports.bunker_repository import BunkerRepository
from src.domain.ports.catalog_provider import CatalogProvider
from src.infrastructure.database.models.reference import BunkerModel, GeometryModel

_EXISTS = text("SELECT EXISTS (SELECT 1 FROM bunkers WHERE id = :id)")

_LIST_BUNKERS = text("""
    SELECT b.id,
           b.name,
           (n.last_seen_at IS NOT NULL
            AND n.last_seen_at >= now() - make_interval(secs => :stale)) AS online
    FROM bunkers b
    LEFT JOIN edge_nodes n ON n.bunker_id = b.id
    ORDER BY b.id
""")


class SqlBunkerRepository(BunkerRepository):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        catalog: CatalogProvider,
    ) -> None:
        self._sessions = sessions
        self._catalog = catalog

    async def exists(self, bunker_id: str) -> bool:
        async with self._sessions() as session:
            value = await session.scalar(_EXISTS, {"id": bunker_id})
            return bool(value)

    async def ensure_in_session(self, session: AsyncSession, bunker_id: str) -> None:
        geometry = self._catalog.geometry_for(bunker_id)
        await session.execute(
            pg_insert(BunkerModel)
            .values(id=bunker_id, name=bunker_id)
            .on_conflict_do_nothing(index_elements=[BunkerModel.id])
        )
        await session.execute(
            pg_insert(GeometryModel)
            .values(
                bunker_id=bunker_id,
                shape=geometry.shape.model_dump(mode="json"),
                sensor=geometry.sensor.model_dump(mode="json"),
                beams=[beam.model_dump(mode="json") for beam in geometry.beams],
            )
            .on_conflict_do_nothing(index_elements=[GeometryModel.bunker_id])
        )

    async def list_bunkers(self, *, stale_after_seconds: int) -> list[Bunker]:
        async with self._sessions() as session:
            rows = await session.execute(_LIST_BUNKERS, {"stale": stale_after_seconds})
            return [Bunker(id=r.id, name=r.name, online=bool(r.online)) for r in rows]

    async def get_geometry(self, bunker_id: str) -> Geometry | None:
        async with self._sessions() as session:
            model = await session.get(GeometryModel, bunker_id)
            if model is None:
                return None
            return Geometry.model_validate(
                {
                    "bunker_id": model.bunker_id,
                    "shape": model.shape,
                    "sensor": model.sensor,
                    "beams": model.beams,
                }
            )
