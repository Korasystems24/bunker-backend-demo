"""SqlEventRepository: дедуп событий по PK (bunker_id, event_id)."""

import json
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.edge_event import EdgeEvent
from src.domain.ports.event_repository import EventRepository
from src.domain.value_objects.save_stats import SaveStats


class SqlEventRepository(EventRepository):
    _INSERT_EVENT = text("""
        INSERT INTO edge_events (bunker_id, event_id, ts, type, payload)
        VALUES (:bunker_id, :event_id, :ts, :type, CAST(:payload AS jsonb))
        ON CONFLICT DO NOTHING
        RETURNING event_id
    """)

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save_batch(self, bunker_id: str, events: Sequence[EdgeEvent]) -> SaveStats:
        inserted = 0

        async with self._sessions() as session, session.begin():
            for event in events:
                result = await session.execute(
                    self._INSERT_EVENT,
                    {
                        "bunker_id": bunker_id,
                        "event_id": str(event.event_id),
                        "ts": event.ts,
                        "type": event.type,
                        "payload": json.dumps(event.payload),
                    },
                )
                if result.scalar() is not None:
                    inserted += 1

        return SaveStats(
            received=len(events),
            inserted=inserted,
            duplicates=len(events) - inserted,
        )
