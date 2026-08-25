"""GET /api/v1/bunkers/{bunker_id}/stats?period=day|week|month — серия для графиков."""

from typing import Annotated, Literal

import fastapi

from src.api.deps import ContainerDep
from src.api.schemas.query import SeriesPointOut, StatsOut

router = fastapi.APIRouter(prefix="/api/v1/bunkers", tags=["query"])


@router.get("/{bunker_id}/stats")
async def get_stats(
    bunker_id: str,
    container: ContainerDep,
    period: Annotated[Literal["day", "week", "month"], fastapi.Query()] = "day",
) -> StatsOut:
    stats = await container.query.get_stats(bunker_id, period)
    return StatsOut(
        period=period,
        min_level=stats.min_level,
        max_level=stats.max_level,
        avg_level=stats.avg_level,
        # Доменные SeriesPoint → DTO: явная конвертация слоёв.
        series=[SeriesPointOut.model_validate(p.model_dump()) for p in stats.series],
    )
