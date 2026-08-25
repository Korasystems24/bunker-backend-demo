"""SqlHealthRepository: upsert последнего снимка edge-узла и чтение состояний."""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.edge_node_state import EdgeNodeState
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.ports.health_repository import HealthRepository
from src.infrastructure.database.repositories.nodes import node_id_for_bunker

# online вычисляется по свежести касания (dead-man read-side);
# SilenceMonitor в шаге 4 формализует это фоновыми алертами.
# cpu/ram/disk округляются до 1 знака — формат мока (REAL даёт шум float4).
_LIST_STATES = text("""
    SELECT node_id,
           bunker_id,
           last_seen_at,
           round(cpu::numeric, 1)::double precision  AS cpu,
           round(ram::numeric, 1)::double precision  AS ram,
           round(disk::numeric, 1)::double precision AS disk,
           (last_seen_at IS NOT NULL
            AND last_seen_at >= now() - make_interval(secs => :stale)) AS online
    FROM edge_nodes
    ORDER BY node_id
""")


class SqlHealthRepository(HealthRepository):
    # cpu/ram/disk — колонки из схемы v1, в них пишутся *_percent агента.
    # ts агента сохраняется в edge_time (контроль drift часов узла).
    _UPSERT_NODE = text("""
        INSERT INTO edge_nodes
            (node_id, bunker_id, last_seen_at, cpu, ram, disk, edge_time, status,
             workers, pending_count, quarantined_count, free_bytes, storage_paused)
        VALUES
            (:node_id, :bunker_id, now(), :cpu, :ram, :disk, :edge_time, 'online',
             CAST(:workers AS jsonb), :pending_count, :quarantined_count,
             :free_bytes, :storage_paused)
        ON CONFLICT (node_id) DO UPDATE SET
            bunker_id = EXCLUDED.bunker_id,
            last_seen_at = now(),
            cpu = EXCLUDED.cpu,
            ram = EXCLUDED.ram,
            disk = EXCLUDED.disk,
            edge_time = EXCLUDED.edge_time,
            status = 'online',
            workers = EXCLUDED.workers,
            pending_count = EXCLUDED.pending_count,
            quarantined_count = EXCLUDED.quarantined_count,
            free_bytes = EXCLUDED.free_bytes,
            storage_paused = EXCLUDED.storage_paused
    """)

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def upsert(self, snapshot: HealthSnapshot, *, bunker_id: str) -> None:
        # status='online' при каждом касании; в offline переводит SilenceMonitor.
        workers_json = {
            name: worker.model_dump(mode="json") for name, worker in snapshot.workers.items()
        }
        async with self._sessions() as session, session.begin():
            await session.execute(
                self._UPSERT_NODE,
                {
                    "node_id": node_id_for_bunker(bunker_id),
                    "bunker_id": bunker_id,
                    "cpu": snapshot.cpu_percent,
                    "ram": snapshot.memory_percent,
                    "disk": snapshot.disk_percent,
                    "edge_time": snapshot.ts,
                    "workers": json.dumps(workers_json),
                    "pending_count": snapshot.pending_count,
                    "quarantined_count": snapshot.quarantined_count,
                    "free_bytes": snapshot.free_bytes,
                    "storage_paused": snapshot.storage_paused,
                },
            )

    async def list_states(self, *, stale_after_seconds: int) -> list[EdgeNodeState]:
        async with self._sessions() as session:
            rows = await session.execute(_LIST_STATES, {"stale": stale_after_seconds})
            return [
                EdgeNodeState(
                    node_id=r.node_id,
                    bunker_id=r.bunker_id,
                    online=bool(r.online),
                    last_seen_at=r.last_seen_at,
                    cpu=r.cpu,
                    ram=r.ram,
                    disk=r.disk,
                )
                for r in rows
            ]
