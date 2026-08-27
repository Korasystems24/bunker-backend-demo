"""GET /api/v1/bunkers/{bunker_id}/buildup — зоны налипания (эвристика v1).

severity/score/threshold/algorithm_version отдаются фронту как непрозрачные
значения бэкенда. Зоны посчитаны на ингесте (compute-on-write).
"""

from fastapi import APIRouter

from src.api.deps import ContainerDep
from src.api.schemas.query import AxisZoneOut, BuildupOut

router = APIRouter(prefix="/api/v1/bunkers", tags=["query"])


@router.get("/{bunker_id}/buildup")
async def get_buildup(bunker_id: str, container: ContainerDep) -> BuildupOut:
    snapshot = await container.query.get_buildup(bunker_id)
    return BuildupOut(
        bunker_id=bunker_id,
        ts=snapshot.ts,
        threshold_m=container.query.buildup_threshold_m,
        algorithm_version=snapshot.algorithm_version,
        zones=[
            AxisZoneOut(
                axis=z.axis,
                severity=z.severity,
                score=z.score,
                deviation_m=z.deviation_m,
                affected_positions=list(z.affected_positions),
            )
            for z in snapshot.zones
        ],
    )
