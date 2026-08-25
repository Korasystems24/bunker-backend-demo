"""Полезная нагрузка событий edge — байтовая копия контракта EdgePC
(src/domain/value_objects/event_payload.py, extra="forbid")."""

import uuid

import pydantic


class RadarDown(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    reason: str


class RadarRecovered(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    downtime_seconds: float = pydantic.Field(ge=0, allow_inf_nan=False)


class PacketQuarantined(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    telemetry_packet_id: int = pydantic.Field(ge=1)
    telemetry_packet_event_id: uuid.UUID
    attempts: int = pydantic.Field(ge=1)


class WorkerRestarted(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    worker: str


class WorkerFatal(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    worker: str
    reason: str
    restartable: bool
