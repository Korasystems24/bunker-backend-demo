"""GET /api/v1/bunkers/{bunker_id}/buildup — зоны налипания (эвристика v1).

severity/score/threshold отдаются фронту как непрозрачные значения бэкенда.
"""

from fastapi import APIRouter

from src.api.deps import ContainerDep
from src.api.schemas.query import AxisZoneOut, BuildupOut

router = APIRouter(prefix="/api/v1/bunkers", tags=["query"])


@router.get("/{bunker_id}/buildup")
async def get_buildup(bunker_id: str, container: ContainerDep) -> BuildupOut:
    measurement, zones = await container.query.get_buildup(bunker_id)
    return BuildupOut(
        bunker_id=bunker_id,
        ts=measurement.ts,
        threshold_m=container.query.buildup_threshold_m,
        zones=[
            AxisZoneOut(
                axis=z.axis,
                severity=z.severity,
                score=z.score,
                deviation_m=z.deviation_m,
                affected_positions=list(z.affected_positions),
            )
            for z in zones
        ],
    )
