"""Атомарная граница записи одного ingest-запроса."""

import uuid
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.telemetry_record import TelemetryRecord


class IngestionTransaction(Protocol):
    async def reserve_telemetry(self, event_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        ...

    async def save_telemetry(self, records: Sequence[TelemetryRecord]) -> None:
        ...

    async def save_events(self, events: Sequence[EdgeEvent]) -> int:
        ...

    async def save_health(self, snapshot: HealthSnapshot) -> None:
        ...


class IngestionUnitOfWork(Protocol):
    def transaction(
        self, bunker_id: str
    ) -> AbstractAsyncContextManager[IngestionTransaction, bool | None]:
        ...
