"""Read-порт временных рядов для Query API."""

from datetime import datetime
from typing import Protocol

from src.domain.entities.measurement import Measurement
from src.domain.value_objects.beam_reading import BeamReading
from src.domain.value_objects.buildup_snapshot import BuildupSnapshot
from src.domain.value_objects.stats_snapshot import StatsSnapshot


class MeasurementRepository(Protocol):
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

    async def get_stats(self, bunker_id: str, *, frm: datetime) -> StatsSnapshot | None:
        """Часовые бакеты из continuous aggregate; None — если пусто."""
        ...

    async def get_latest_buildup(self, bunker_id: str) -> BuildupSnapshot | None:
        """Последний снимок зон (compute-on-write). None — если ещё не считали."""
        ...
