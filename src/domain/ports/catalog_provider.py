"""Порт источника конфигурации каталога."""

from typing import Protocol

from src.domain.entities.catalog import BunkerCatalog
from src.domain.entities.geometry import Geometry


class CatalogProvider(Protocol):
    @property
    def catalog(self) -> BunkerCatalog:
        ...

    def geometry_for(self, bunker_id: str) -> Geometry:
        """Создать геометрию для непрозрачного bunker_id по шаблону каталога."""
        ...
