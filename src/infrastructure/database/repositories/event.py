"""SqlEventRepository: дедуп событий по PK (bunker_id, event_id)."""

import json
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.edge_event import EdgeEvent
from src.infrastructure.database.repositories.nodes import touch_node


class SqlEventRepository:
    _INSERT_EVENTS = text("""
        INSERT INTO edge_events (bunker_id, event_id, ts, type, payload)
        SELECT :bunker_id, item.event_id, item.ts, item.type, item.payload
        FROM jsonb_to_recordset(CAST(:events AS jsonb)) AS item(
            event_id uuid,
            ts timestamptz,
            type text,
            payload jsonb
        )
        ON CONFLICT DO NOTHING
        RETURNING event_id
    """)

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save_batch_in_session(
        self,
        session: AsyncSession,
        bunker_id: str,
        events: Sequence[EdgeEvent],
    ) -> int:
        serialized = [
            {
                "event_id": str(event.event_id),
                "ts": event.ts.isoformat(),
                "type": event.type,
                "payload": event.payload.model_dump(mode="json"),
            }
            for event in events
        ]
        inserted = 0
        if serialized:
            rows = await session.execute(
                self._INSERT_EVENTS,
                {
                    "bunker_id": bunker_id,
                    "events": json.dumps(serialized),
                },
            )
            inserted = len(rows.all())
        await touch_node(session, bunker_id)
        return inserted
