"""DTO выдачи фронту.

Отступления от сырого ingest:
- списочная /measurements не отдаёт beams (защита от лагов фронта);
- limit жёстко ограничен сервером (clamp в QueryService).
"""

from datetime import datetime
from typing import Any

import pydantic


class BunkerOut(pydantic.BaseModel):
    id: str
    name: str
    online: bool
    # Идентификатор геометрии ('geom-bunker-1'); выводится из id,
    # потому что в БД геометрия ключуется самим бункером.
    geometry_id: str


class GeometryBeamOut(pydantic.BaseModel):
    beam_name: str
    axis: str
    position: int
    x: float
    y: float
    z: float


class GeometryOut(pydantic.BaseModel):
    bunker_id: str
    shape: dict[str, Any]
    sensor: dict[str, Any]
    beams: list[GeometryBeamOut]


class BeamReadingOut(pydantic.BaseModel):
    beam_name: str
    height: float | None = None
    status: str = ""


class MeasurementOut(pydantic.BaseModel):
    """Списочное представление: beams не отдаётся вовсе (риск лагов фронта)."""

    id: int
    ts: datetime
    avg_level: float | None = None
    min_level: float | None = None
    max_level: float | None = None
    volume: float | None = None
    mass: float | None = None


class LatestMeasurementOut(MeasurementOut):
    """Детальное представление /latest: измерение вместе с 64 лучами."""

    beams: list[BeamReadingOut]


class MeasurementsPageOut(pydantic.BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MeasurementOut]


class SeriesPointOut(pydantic.BaseModel):
    ts: datetime
    avg_level: float | None = None
    min_level: float | None = None
    max_level: float | None = None
    mass: float | None = None
    volume: float | None = None


class StatsOut(pydantic.BaseModel):
    period: str
    min_level: float | None = None
    max_level: float | None = None
    avg_level: float | None = None
    series: list[SeriesPointOut]


class AxisZoneOut(pydantic.BaseModel):
    axis: str
    severity: str
    score: float
    deviation_m: float
    affected_positions: list[int] = pydantic.Field(default_factory=list)


class BuildupOut(pydantic.BaseModel):
    bunker_id: str
    ts: datetime
    threshold_m: float
    algorithm_version: str
    zones: list[AxisZoneOut]


class EdgePcOut(pydantic.BaseModel):
    node_id: str
    online: bool
    last_pulse: datetime | None = None
    cpu: float | None = None
    ram: float | None = None
    disk: float | None = None


class EdgeHealthOut(pydantic.BaseModel):
    edge_pcs: list[EdgePcOut]
