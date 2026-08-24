"""Порт хранилища измерений."""

from collections.abc import Sequence
from typing import Protocol

from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.value_objects.save_stats import SaveStats


class MeasurementRepository(Protocol):
    async def save_batch(self, bunker_id: str, records: Sequence[TelemetryRecord]) -> SaveStats:
        """Сохранить батч одной транзакцией; повторы гасятся как дубли."""
        ...
