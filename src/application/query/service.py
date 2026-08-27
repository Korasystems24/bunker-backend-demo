"""QueryService: read-контур CQRS-lite — сценарии выдачи данных фронту.

beams отдаются только в /latest, limit жёстко ограничен, графики строятся
только из серверных бакетов stats (continuous aggregate measurements_hourly).
"""

from datetime import UTC, datetime, timedelta

from src.domain.entities.bunker import Bunker
from src.domain.entities.edge_node_state import EdgeNodeState
from src.domain.entities.geometry import Geometry
from src.domain.entities.measurement import Measurement
from src.domain.exceptions import (
    BunkerNotFoundError,
    MeasurementsNotFoundError,
    NoDataNotFoundError,
)
from src.domain.ports.bunker_repository import BunkerRepository
from src.domain.ports.health_repository import HealthRepository
from src.domain.ports.measurement_repository import MeasurementRepository
from src.domain.value_objects.beam_reading import BeamReading
from src.domain.value_objects.buildup_snapshot import BuildupSnapshot
from src.domain.value_objects.stats_snapshot import StatsSnapshot

# Защита фронта от лагов: жёсткий потолок страницы списка.
MAX_PAGE_LIMIT = 100

# Горизонт назад. Размер бакета для всех периодов — 1 час (cagg).
_PERIOD_HORIZON: dict[str, timedelta] = {
    "day": timedelta(hours=24),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}


class QueryService:
    def __init__(
        self,
        measurements: MeasurementRepository,
        bunkers: BunkerRepository,
        health: HealthRepository,
        *,
        edge_stale_after_sec: int,
        buildup_threshold_m: float,
    ) -> None:
        self._measurements = measurements
        self._bunkers = bunkers
        self._health = health
        self._edge_stale_after_sec = edge_stale_after_sec
        self._deviation_threshold_m = buildup_threshold_m

    async def list_bunkers(self) -> list[Bunker]:
        return await self._bunkers.list_bunkers(
            stale_after_seconds=self._edge_stale_after_sec,
        )

    async def get_geometry(self, bunker_id: str) -> Geometry:
        geometry = await self._bunkers.get_geometry(bunker_id)
        if geometry is None:
            raise BunkerNotFoundError()
        return geometry

    async def get_latest_measurement(self, bunker_id: str) -> tuple[Measurement, list[BeamReading]]:
        await self._ensure_bunker(bunker_id)
        latest = await self._measurements.get_latest_with_beams(bunker_id)
        if latest is None:
            raise MeasurementsNotFoundError()
        return latest

    async def get_measurements_page(
        self,
        bunker_id: str,
        *,
        frm: datetime | None,
        to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[Measurement]]:
        """Возвращает (total, items); beams в списке не отдаём никогда."""
        await self._ensure_bunker(bunker_id)
        clamped_limit = min(limit, MAX_PAGE_LIMIT)
        total = await self._measurements.count_range(bunker_id, frm=frm, to=to)
        if total == 0:
            return 0, []
        items = await self._measurements.get_range(
            bunker_id,
            frm=frm,
            to=to,
            limit=clamped_limit,
            offset=offset,
        )
        return total, items

    async def get_stats(self, bunker_id: str, period: str) -> StatsSnapshot:
        """Часовые бакеты за период; пустой период — 404, без подстановки старых точек."""
        horizon = _PERIOD_HORIZON[period]
        await self._ensure_bunker(bunker_id)

        frm = datetime.now(UTC) - horizon
        stats = await self._measurements.get_stats(bunker_id, frm=frm)
        if stats is None:
            raise NoDataNotFoundError()
        return stats

    async def list_edge_nodes(self) -> list[EdgeNodeState]:
        return await self._health.list_states(
            stale_after_seconds=self._edge_stale_after_sec,
        )

    async def get_buildup(self, bunker_id: str) -> BuildupSnapshot:
        """Последние зоны из buildup_zones (посчитаны на ингесте)."""
        await self._ensure_bunker(bunker_id)
        snapshot = await self._measurements.get_latest_buildup(bunker_id)
        if snapshot is None:
            raise NoDataNotFoundError()
        return snapshot

    @property
    def buildup_threshold_m(self) -> float:
        return self._deviation_threshold_m

    async def _ensure_bunker(self, bunker_id: str) -> None:
        if not await self._bunkers.exists(bunker_id):
            raise BunkerNotFoundError()
