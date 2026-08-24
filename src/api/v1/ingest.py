"""POST-ручки приёма данных от edge: /telemetry, /events, /health.

Семантика ответов по контракту: 200 — успех (включая полный дубль),
401/403 — токен, 422 — ошибка валидации (batch отклоняется целиком).
"""

import fastapi

from src.api.deps import ContainerDep, require_edge_api_key
from src.api.schemas.ingest import (
    EventsRequest,
    HealthAccepted,
    HealthRequest,
    IngestAccepted,
    TelemetryRequest,
)

router = fastapi.APIRouter(
    prefix="/api/v1",
    tags=["ingest"],
    dependencies=[fastapi.Depends(require_edge_api_key)],
)


@router.post("/telemetry")
async def post_telemetry(payload: TelemetryRequest, container: ContainerDep) -> IngestAccepted:
    stats = await container.ingestion.ingest_telemetry(payload.bunker_id, payload.packets)
    return IngestAccepted(
        received=stats.received,
        inserted=stats.inserted,
        duplicates=stats.duplicates,
    )


@router.post("/events")
async def post_events(payload: EventsRequest, container: ContainerDep) -> IngestAccepted:
    stats = await container.ingestion.ingest_events(payload.bunker_id, payload.events)
    return IngestAccepted(
        received=stats.received,
        inserted=stats.inserted,
        duplicates=stats.duplicates,
    )


@router.post("/health")
async def post_health(payload: HealthRequest, container: ContainerDep) -> HealthAccepted:
    await container.ingestion.ingest_health(payload)
    return HealthAccepted()
