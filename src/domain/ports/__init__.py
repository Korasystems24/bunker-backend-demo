"""Порты домена: интерфейсы хранилищ (реализации — в infrastructure)."""

from src.domain.ports.event_repository import EventRepository
from src.domain.ports.health_repository import HealthRepository
from src.domain.ports.measurement_repository import MeasurementRepository

__all__ = ["EventRepository", "HealthRepository", "MeasurementRepository"]
