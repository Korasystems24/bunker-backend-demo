"""Порт хранилища состояния edge-узлов."""

from typing import Protocol

from src.domain.entities.edge_node_state import EdgeNodeState
from src.domain.entities.health_snapshot import HealthSnapshot


class HealthRepository(Protocol):
    async def upsert(self, snapshot: HealthSnapshot, *, bunker_id: str) -> None:
        """Обновить последний снимок узла (last_seen_at = now(); node_id
        выводится из bunker_id — агент не шлёт node_id)."""
        ...

    async def list_states(self, *, stale_after_seconds: int) -> list[EdgeNodeState]:
        """Последние снимки всех узлов; online = касание свежее порога."""
        ...
