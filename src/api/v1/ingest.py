"""POST-ручки приёма данных от edge: /telemetry, /events, /health.

Семантика ответов по контракту: 200 — успех (включая полный дубль),
401/403 — Bearer-токен, 422 — ошибка валидации (batch отклоняется целиком).
"""

import fastapi

from src.api.deps import ContainerDep, require_edge_token
from src.api.mappers.ingest import event_to_domain, health_to_domain, telemetry_packet_to_domain
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
    dependencies=[fastapi.Depends(require_edge_token)],
)


@router.post("/telemetry")
async def post_telemetry(payload: TelemetryRequest, container: ContainerDep) -> IngestAccepted:
    stats = await container.ingestion.ingest_telemetry(
        payload.bunker_id,
        [telemetry_packet_to_domain(packet) for packet in payload.packets],
    )
    return IngestAccepted(
        received=stats.received,
        inserted=stats.inserted,
        duplicates=stats.duplicates,
    )


@router.post("/events")
async def post_events(payload: EventsRequest, container: ContainerDep) -> IngestAccepted:
    stats = await container.ingestion.ingest_events(
        payload.bunker_id,
        [event_to_domain(event) for event in payload.events],
    )
    return IngestAccepted(
        received=stats.received,
        inserted=stats.inserted,
        duplicates=stats.duplicates,
    )


@router.post("/health")
async def post_health(payload: HealthRequest, container: ContainerDep) -> HealthAccepted:
    await container.ingestion.ingest_health(payload.bunker_id, health_to_domain(payload))
    return HealthAccepted()
