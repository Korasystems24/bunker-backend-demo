"""GET-ручки фронта: /bunkers, /geometry (ETag), /measurements[/latest]."""

import hashlib
import json
from datetime import datetime
from typing import Annotated

import fastapi
from fastapi.responses import JSONResponse, Response

from src.api.deps import ContainerDep
from src.api.schemas.query import (
    BeamReadingOut,
    BunkerOut,
    GeometryBeamOut,
    GeometryOut,
    LatestMeasurementOut,
    MeasurementOut,
    MeasurementsPageOut,
)
from src.application.query.service import MAX_PAGE_LIMIT
from src.domain.entities.measurement import Measurement
from src.domain.exceptions import DomainError

router = fastapi.APIRouter(prefix="/api/v1/bunkers", tags=["query"])

# Геометрия меняется только при пересиде конфигуратора; ETag даёт 304,
# а Cache-Control снимает повторные запросы в окне опроса фронта.
_GEOMETRY_CACHE_CONTROL = "public, max-age=300"


def _measurement_out(measurement: Measurement) -> MeasurementOut:
    if measurement.id is None:
        # На read-пути id присваивается триггером БД; его отсутствие — баг.
        raise DomainError("measurement row without id")
    return MeasurementOut(
        id=measurement.id,
        ts=measurement.ts,
        avg_level=measurement.avg_level,
        min_level=measurement.min_level,
        max_level=measurement.max_level,
        volume=measurement.volume,
        mass=measurement.mass,
    )


@router.get("")
async def list_bunkers(container: ContainerDep) -> list[BunkerOut]:
    bunkers = await container.query.list_bunkers()
    # geometry_id выводится из id бункера ('geom-bunker-1'):
    # в БД геометрия ключуется самим бункером.
    return [
        BunkerOut(id=b.id, name=b.name, online=b.online, geometry_id=f"geom-{b.id}")
        for b in bunkers
    ]


@router.get("/{bunker_id}/geometry")
async def get_geometry(
    bunker_id: str,
    container: ContainerDep,
    if_none_match: Annotated[str | None, fastapi.Header()] = None,
) -> Response:
    geometry = await container.query.get_geometry(bunker_id)
    payload = GeometryOut(
        bunker_id=geometry.bunker_id,
        shape=geometry.shape.model_dump(mode="json"),
        sensor=geometry.sensor.model_dump(mode="json"),
        beams=[
            GeometryBeamOut.model_validate(beam.model_dump(mode="json"))
            for beam in geometry.beams
        ],
    ).model_dump(mode="json")

    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    etag = f'"{hashlib.sha256(body.encode("utf-8")).hexdigest()}"'

    if if_none_match is not None and etag in {tag.strip() for tag in if_none_match.split(",")}:
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": _GEOMETRY_CACHE_CONTROL},
        )

    return JSONResponse(
        content=payload,
        headers={"ETag": etag, "Cache-Control": _GEOMETRY_CACHE_CONTROL},
    )


@router.get("/{bunker_id}/measurements/latest")
async def get_latest_measurement(bunker_id: str, container: ContainerDep) -> LatestMeasurementOut:
    measurement, beams = await container.query.get_latest_measurement(bunker_id)
    return LatestMeasurementOut(
        **_measurement_out(measurement).model_dump(),
        beams=[
            BeamReadingOut(beam_name=b.beam_name, height=b.height, status=b.status)
            for b in beams
        ],
    )


@router.get("/{bunker_id}/measurements")
async def list_measurements(
    bunker_id: str,
    container: ContainerDep,
    frm: Annotated[datetime | None, fastapi.Query(alias="from")] = None,
    to: Annotated[datetime | None, fastapi.Query()] = None,
    limit: Annotated[int, fastapi.Query(ge=1)] = 50,
    offset: Annotated[int, fastapi.Query(ge=0)] = 0,
) -> MeasurementsPageOut:
    """Список без beams: 500 записей × 64 луча — путь к лагам фронта (риск 7.1)."""
    total, items = await container.query.get_measurements_page(
        bunker_id,
        frm=frm,
        to=to,
        limit=limit,
        offset=offset,
    )
    return MeasurementsPageOut(
        total=total,
        limit=min(limit, MAX_PAGE_LIMIT),
        offset=offset,
        items=[_measurement_out(m) for m in items],
    )
