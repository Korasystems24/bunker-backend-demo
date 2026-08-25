"""QueryService: read-контур CQRS-lite — сценарии выдачи данных фронту.

Формат ответов воспроизводит мок 1:1 (docs/backend-demo-plan.md, блок B):
beams отдаются только в latest, limit жёстко ограничен, графики строятся
только из серверных бакетов stats.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from src.application.buildup.detector import RadialSlopeDeviationDetector
from src.config.settings import BuildupSettings
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
from src.domain.value_objects.axis_zone import AxisZone
from src.domain.value_objects.beam_reading import BeamReading
from src.domain.value_objects.stats_snapshot import StatsSnapshot

if TYPE_CHECKING:
    from src.domain.ports.buildup_detector import BuildupDetector

# Защита фронта от лагов: жёсткий потолок списка. Мок ограничивает страницу
# сотней (API.md «limit максимум 100»), фронт больше никогда не запрашивает.
MAX_PAGE_LIMIT = 100
# Fallback мока для пустого периода: последние N измерений вне периода.
RECENT_FALLBACK_LIMIT = 10

# Период → (горизонт назад, размер бакета в секундах) — константы мока:
# day → 24 точки по часу, week → 28 точек по 6 часов, month → 30 точек по суткам.
_PERIOD_PARAMS: dict[str, tuple[timedelta, int]] = {
    "day": (timedelta(hours=24), 3600),
    "week": (timedelta(days=7), 6 * 3600),
    "month": (timedelta(days=30), 86400),
}


class QueryService:
    def __init__(
        self,
        measurements: MeasurementRepository,
        bunkers: BunkerRepository,
        health: HealthRepository,
        *,
        edge_stale_after_sec: int,
        buildup: BuildupSettings | None = None,
    ) -> None:
        self._measurements = measurements
        self._bunkers = bunkers
        self._health = health
        self._edge_stale_after_sec = edge_stale_after_sec
        buildup = buildup or BuildupSettings()
        # Эвристика v1; Strategy заменяется без изменения контракта.
        self._buildup_detector: BuildupDetector = RadialSlopeDeviationDetector(
            outer_position_threshold=buildup.outer_position_threshold,
            deviation_threshold_m=buildup.deviation_threshold_m,
        )
        self._deviation_threshold_m = buildup.deviation_threshold_m

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
        """Бакеты за период; при пустом периоде — fallback мока на последние N."""
        horizon, bucket_secs = _PERIOD_PARAMS[period]
        await self._ensure_bunker(bunker_id)

        frm = datetime.now(UTC) - horizon
        stats = await self._measurements.get_stats(bunker_id, frm=frm, bucket_secs=bucket_secs)
        if stats is not None:
            return stats
        fallback = await self._measurements.get_recent_stats(
            bunker_id,
            last_n=RECENT_FALLBACK_LIMIT,
            bucket_secs=bucket_secs,
        )
        if fallback is None:
            raise NoDataNotFoundError()
        return fallback

    async def list_edge_nodes(self) -> list[EdgeNodeState]:
        return await self._health.list_states(
            stale_after_seconds=self._edge_stale_after_sec,
        )

    async def get_buildup(self, bunker_id: str) -> tuple[Measurement, list[AxisZone]]:
        """Зоны налипания по последнему измерению (on-read, как в моке).

        Возвращает (измерение-источник, зоны); severity/score непрозрачны для
        фронта. Пустые данные → "No data" (текст мока), не "No measurements".
        """
        await self._ensure_bunker(bunker_id)
        latest = await self._measurements.get_latest_with_beams(bunker_id)
        if latest is None:
            raise NoDataNotFoundError()
        measurement, beams = latest
        return measurement, self._buildup_detector.detect(beams)

    @property
    def buildup_threshold_m(self) -> float:
        return self._deviation_threshold_m

    async def _ensure_bunker(self, bunker_id: str) -> None:
        # Справочник — источник истины по существованию бункера.
        bunkers = await self.list_bunkers()
        if all(b.id != bunker_id for b in bunkers):
            raise BunkerNotFoundError()
