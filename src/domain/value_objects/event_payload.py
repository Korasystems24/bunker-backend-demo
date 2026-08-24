"""Полезная нагрузка событий edge (контракт фазы 7а)."""

import uuid

import pydantic


class RadarDown(pydantic.BaseModel):
    reason: str


class RadarRecovered(pydantic.BaseModel):
    downtime_s: float = pydantic.Field(ge=0)


class PacketQuarantined(pydantic.BaseModel):
    packet_event_id: uuid.UUID


class WorkerRestarted(pydantic.BaseModel):
    worker: str


class FatalError(pydantic.BaseModel):
    error: str
