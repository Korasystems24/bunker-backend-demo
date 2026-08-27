"""Общая логика edge_nodes: непрозрачная идентичность и last_seen_at."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def node_id_for_bunker(bunker_id: str) -> str:
    """Не интерпретировать внешний id: один edge-узел идентифицируется bunker_id."""
    return bunker_id


# Касание телеметрией/событиями продлевает жизнь узлу (dead-man).
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

_PREV_STATUS = text("SELECT status FROM edge_nodes WHERE node_id = :node_id")

# Закрыть открытый silence_started и записать silence_resolved (возврат данных).
_RESOLVE_SILENCE = text("""
    WITH closed AS (
        UPDATE alerts
        SET resolved_at = now()
        WHERE node_id = :node_id
          AND type = 'silence_started'
          AND resolved_at IS NULL
        RETURNING node_id
    )
    INSERT INTO alerts (node_id, type, last_seen_at)
    SELECT node_id, 'silence_resolved', now() FROM closed
""")


async def resolve_silence_if_offline(
    session: AsyncSession, node_id: str, previous_status: str | None
) -> None:
    if previous_status == "offline":
        await session.execute(_RESOLVE_SILENCE, {"node_id": node_id})


async def previous_status(session: AsyncSession, node_id: str) -> str | None:
    return (await session.execute(_PREV_STATUS, {"node_id": node_id})).scalar()


async def touch_node(session: AsyncSession, bunker_id: str) -> None:
    node_id = node_id_for_bunker(bunker_id)
    prev = await previous_status(session, node_id)
    await session.execute(
        _TOUCH_NODE,
        {"node_id": node_id, "bunker_id": bunker_id},
    )
    await resolve_silence_if_offline(session, node_id, prev)
