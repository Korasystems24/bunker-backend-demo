"""Порт хранилища измерений: write-контур ингеста + read-контур Query API."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from src.domain.entities.measurement import Measurement
from src.domain.entities.telemetry_record import TelemetryRecord
from src.domain.value_objects.beam_reading import BeamReading
from src.domain.value_objects.save_stats import SaveStats
from src.domain.value_objects.stats_snapshot import StatsSnapshot


class MeasurementRepository(Protocol):
    async def save_batch(self, bunker_id: str, records: Sequence[TelemetryRecord]) -> SaveStats:
        """Сохранить батч одной транзакцией; повторы гасятся как дубли."""
        ...

    async def get_latest_with_beams(
        self, bunker_id: str
    ) -> tuple[Measurement, list[BeamReading]] | None:
        """Последнее измерение бункера вместе с его лучами (ручка /latest)."""
        ...

    async def get_range(
        self,
        bunker_id: str,
        *,
        frm: datetime | None,
        to: datetime | None,
        limit: int,
        offset: int,
    ) -> list[Measurement]:
        """Страница диапазона НОВЫМИ вперёд, без лучей (защита от лагов фронта)."""
        ...

    async def count_range(
        self, bunker_id: str, *, frm: datetime | None, to: datetime | None
    ) -> int:
        ...

    async def get_stats(
        self, bunker_id: str, *, frm: datetime, bucket_secs: int
    ) -> StatsSnapshot | None:
        """Серверные бакеты по сырым измерениям периода; None — если пусто."""
        ...

    async def get_recent_stats(
        self, bunker_id: str, *, last_n: int, bucket_secs: int
    ) -> StatsSnapshot | None:
        """Та же агрегация по последним N измерениям вне периода (fallback мока)."""
        ...
