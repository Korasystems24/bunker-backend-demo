"""Порт справочника бункеров и их геометрии (read-сторона Query API)."""

from typing import Protocol

from src.domain.entities.bunker import Bunker
from src.domain.entities.geometry import Geometry


class BunkerRepository(Protocol):
    async def list_bunkers(self, *, stale_after_seconds: int) -> list[Bunker]:
        """Список бункеров с признаком online (свежесть касания узла edge)."""
        ...

    async def exists(self, bunker_id: str) -> bool:
        """Есть ли бункер в справочнике."""
        ...

    async def get_geometry(self, bunker_id: str) -> Geometry | None:
        """Геометрия из справочника."""
        ...
