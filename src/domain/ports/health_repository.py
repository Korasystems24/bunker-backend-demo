"""Порт хранилища состояния edge-узлов."""

from typing import Protocol

from src.domain.entities.health_snapshot import HealthSnapshot


class HealthRepository(Protocol):
    async def upsert(self, snapshot: HealthSnapshot) -> None:
        """Обновить последний снимок узла (last_seen_at = now())."""
        ...
