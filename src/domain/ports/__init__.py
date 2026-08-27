"""Порты домена: интерфейсы хранилищ (реализации — в infrastructure)."""

from src.domain.ports.bunker_repository import BunkerRepository
from src.domain.ports.catalog_provider import CatalogProvider
from src.domain.ports.health_repository import HealthRepository
from src.domain.ports.ingestion_uow import IngestionUnitOfWork
from src.domain.ports.measurement_repository import MeasurementRepository

__all__ = [
    "BunkerRepository",
    "CatalogProvider",
    "HealthRepository",
    "IngestionUnitOfWork",
    "MeasurementRepository",
]
