"""SqlHealthRepository: upsert последнего снимка edge-узла."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.ports.health_repository import HealthRepository


class SqlHealthRepository(HealthRepository):
    _UPSERT_NODE = text("""
        INSERT INTO edge_nodes
            (node_id, bunker_id, last_seen_at, cpu, ram, disk, edge_time, status)
        VALUES
            (:node_id, :bunker_id, now(), :cpu, :ram, :disk, :edge_time, 'online')
        ON CONFLICT (node_id) DO UPDATE SET
            bunker_id = EXCLUDED.bunker_id,
            last_seen_at = now(),
            cpu = EXCLUDED.cpu,
            ram = EXCLUDED.ram,
            disk = EXCLUDED.disk,
            edge_time = EXCLUDED.edge_time,
            status = 'online'
    """)

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def upsert(self, snapshot: HealthSnapshot) -> None:
        # status='online' при каждом касании; в offline переводит SilenceMonitor.
        async with self._sessions() as session, session.begin():
            await session.execute(
                self._UPSERT_NODE,
                {
                    "node_id": snapshot.node_id,
                    "bunker_id": snapshot.bunker_id,
                    "cpu": snapshot.cpu,
                    "ram": snapshot.ram,
                    "disk": snapshot.disk,
                    "edge_time": snapshot.edge_time,
                },
            )
