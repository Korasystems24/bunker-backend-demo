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

    async def mark_silent_nodes(self, *, stale_after_seconds: int) -> list[str]:
        """Узлы с last_seen старше порога → status='offline' + silence_started.

        Возвращает node_id, которые только что перешли в offline.
        Узлы без last_seen_at (никогда не подключались) не трогает.
        """
        ...

    async def resolve_recovered_nodes(self) -> list[str]:
        """Открытый silence_started при status='online' → закрыть + silence_resolved."""
        ...
