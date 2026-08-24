"""Порт хранилища событий edge."""

from collections.abc import Sequence
from typing import Protocol

from src.domain.entities.edge_event import EdgeEvent
from src.domain.value_objects.save_stats import SaveStats


class EventRepository(Protocol):
    async def save_batch(self, bunker_id: str, events: Sequence[EdgeEvent]) -> SaveStats:
        """Сохранить события одной транзакцией; повторы гасятся как дубли."""
        ...
