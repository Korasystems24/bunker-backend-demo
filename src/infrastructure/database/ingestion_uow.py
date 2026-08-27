"""SQLAlchemy-реализация атомарной границы ingest."""

import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.ports.ingestion_uow import IngestionTransaction, IngestionUnitOfWork
from src.infrastructure.database.repositories.bunker import SqlBunkerRepository
from src.infrastructure.database.repositories.event import SqlEventRepository
from src.infrastructure.database.repositories.health import SqlHealthRepository
from src.infrastructure.database.repositories.measurement import SqlMeasurementRepository


class SqlIngestionTransaction(IngestionTransaction):
    _RESERVE_TELEMETRY = text("""
        INSERT INTO ingest_ledger (bunker_id, event_id)
        SELECT :bunker_id, event_id
        FROM unnest(CAST(:event_ids AS uuid[])) AS event_id
        ON CONFLICT DO NOTHING
        RETURNING event_id
    """)

    def __init__(
        self,
        session: AsyncSession,
        bunker_id: str,
        *,
        measurements: SqlMeasurementRepository,
        events: SqlEventRepository,
        health: SqlHealthRepository,
    ) -> None:
        self._session = session
        self._bunker_id = bunker_id
        self._measurements = measurements
        self._events = events
        self._health = health

    async def reserve_telemetry(self, event_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        if not event_ids:
            return set()
        rows = await self._session.execute(
            self._RESERVE_TELEMETRY,
            {
                "bunker_id": self._bunker_id,
                "event_ids": [str(event_id) for event_id in event_ids],
            },
        )
        return {uuid.UUID(str(row.event_id)) for row in rows}

    async def save_telemetry(self, records: Sequence[TelemetryRecord]) -> None:
        await self._measurements.save_batch_in_session(
            self._session,
            self._bunker_id,
            records,
        )

    async def save_events(self, events: Sequence[EdgeEvent]) -> int:
        return await self._events.save_batch_in_session(
            self._session,
            self._bunker_id,
            events,
        )

    async def save_health(self, snapshot: HealthSnapshot) -> None:
        await self._health.upsert_in_session(
            self._session,
            snapshot,
            bunker_id=self._bunker_id,
        )


class SqlIngestionUnitOfWork(IngestionUnitOfWork):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        bunkers: SqlBunkerRepository,
        measurements: SqlMeasurementRepository,
        events: SqlEventRepository,
        health: SqlHealthRepository,
    ) -> None:
        self._sessions = sessions
        self._bunkers = bunkers
        self._measurements = measurements
        self._events = events
        self._health = health
        self._known_bunkers: set[str] = set()

    async def _provision(self, session: AsyncSession, bunker_id: str) -> bool:
        if bunker_id in self._known_bunkers:
            return False
        await self._bunkers.ensure_in_session(session, bunker_id)
        return True

    @asynccontextmanager
    async def transaction(self, bunker_id: str) -> AsyncGenerator[IngestionTransaction]:
        provisioned = False
        async with self._sessions() as session, session.begin():
            provisioned = await self._provision(session, bunker_id)
            yield SqlIngestionTransaction(
                session,
                bunker_id,
                measurements=self._measurements,
                events=self._events,
                health=self._health,
            )
        if provisioned:
            self._known_bunkers.add(bunker_id)
