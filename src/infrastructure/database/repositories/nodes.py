"""Общая логика таблицы edge_nodes: вывод node_id и касание last_seen_at.

EdgePC не шлёт node_id — один агент на бункер (допущение демо), поэтому
идентичность узла выводится из bunker_id: 'bunker-1' -> 'edge-1'
(тот же правило использует scripts/seed_demo.py и мок).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def node_id_for_bunker(bunker_id: str) -> str:
    return f"edge-{bunker_id.rsplit('-', 1)[-1]}"


# Касание телеметрией/событиями продлевает жизнь узлу (dead-man, шаг 4).
# Строки нет до первого POST /health или бункера нет в справочнике → no-op.
_TOUCH_NODE = text("""
    INSERT INTO edge_nodes (node_id, bunker_id, last_seen_at, status)
    SELECT :node_id, :bunker_id, now(), 'online'
    WHERE EXISTS (SELECT 1 FROM bunkers WHERE id = :bunker_id)
    ON CONFLICT (node_id) DO UPDATE SET
        bunker_id = EXCLUDED.bunker_id,
        last_seen_at = now(),
        status = 'online'
""")


async def touch_node(session: AsyncSession, bunker_id: str) -> None:
    await session.execute(
        _TOUCH_NODE,
        {"node_id": node_id_for_bunker(bunker_id), "bunker_id": bunker_id},
    )
