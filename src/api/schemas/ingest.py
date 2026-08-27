"""HTTP DTO приёма данных от edge; доменные модели здесь не переиспользуются."""

import uuid
from typing import Annotated, Literal, Self

import pydantic

from src.domain.constants import BEAM_COUNT
from src.domain.value_objects.beam_status import BeamStatus

BunkerId = Annotated[str, pydantic.Field(min_length=1, max_length=128)]
FiniteMeasurement = Annotated[float, pydantic.Field(ge=0, allow_inf_nan=False)]


class BeamIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    height: Annotated[float, pydantic.Field(allow_inf_nan=False)] | None
    raw_status: int | None
    status: tuple[BeamStatus, ...]


class TelemetryPacketIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    event_id: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    ts: pydantic.AwareDatetime
    avg_level: FiniteMeasurement | None = None
    mass: FiniteMeasurement | None = None
    volume: FiniteMeasurement | None = None
    beams: Annotated[list[BeamIn], pydantic.Field(min_length=BEAM_COUNT, max_length=BEAM_COUNT)]


class RadarDownIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    reason: str


class RadarRecoveredIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    downtime_seconds: float = pydantic.Field(ge=0, allow_inf_nan=False)


class PacketQuarantinedIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    telemetry_packet_id: int = pydantic.Field(ge=1)
    telemetry_packet_event_id: uuid.UUID
    attempts: int = pydantic.Field(ge=1)


class WorkerRestartedIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    worker: str


class WorkerFatalIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    worker: str
    reason: str
    restartable: bool


EventTypeIn = Literal[
    "radar_down",
    "radar_recovered",
    "packet_quarantined",
    "worker_restarted",
    "fatal_error",
]
EventPayloadIn = (
    RadarDownIn | RadarRecoveredIn | PacketQuarantinedIn | WorkerRestartedIn | WorkerFatalIn
)
_EVENT_PAYLOADS: dict[EventTypeIn, type[EventPayloadIn]] = {
    "radar_down": RadarDownIn,
    "radar_recovered": RadarRecoveredIn,
    "packet_quarantined": PacketQuarantinedIn,
    "worker_restarted": WorkerRestartedIn,
    "fatal_error": WorkerFatalIn,
}


class EventIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    event_id: uuid.UUID
    ts: pydantic.AwareDatetime
    type: EventTypeIn
    payload: EventPayloadIn

    @pydantic.model_validator(mode="after")
    def payload_matches_type(self) -> Self:
        expected = _EVENT_PAYLOADS[self.type]
        if type(self.payload) is not expected:
            raise ValueError(f"{self.type} expects {expected.__name__}")
        return self


class FatalErrorIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    reason: str
    restartable: bool


class WorkerHealthIn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    alive: bool
    last_error: str | None = None
    last_error_at: pydantic.AwareDatetime | None = None
    fatal: FatalErrorIn | None = None


class TelemetryRequest(pydantic.BaseModel):
    """Пакеты как шлёт EdgePC: avg_level и Beam.height — миллиметры."""

    bunker_id: BunkerId
    packets: list[TelemetryPacketIn] = pydantic.Field(min_length=1)


class EventsRequest(pydantic.BaseModel):
    bunker_id: BunkerId
    events: list[EventIn] = pydantic.Field(min_length=1)


class HealthRequest(pydantic.BaseModel):
    """Тело POST /health: снимок узла + bunker_id рядом с ним.

    EdgePC не шлёт node_id; backend хранит bunker_id как непрозрачную
    идентичность узла, не разбирая его формат.
    """

    bunker_id: BunkerId
    ts: pydantic.AwareDatetime
    workers: dict[str, WorkerHealthIn]
    pending_count: int = pydantic.Field(ge=0)
    quarantined_count: int = pydantic.Field(ge=0)
    free_bytes: int = pydantic.Field(ge=0)
    storage_paused: bool
    cpu_percent: float = pydantic.Field(ge=0, le=100, allow_inf_nan=False)
    memory_percent: float = pydantic.Field(ge=0, le=100, allow_inf_nan=False)
    disk_percent: float = pydantic.Field(ge=0, le=100, allow_inf_nan=False)


class IngestAccepted(pydantic.BaseModel):
    received: int
    inserted: int
    duplicates: int


class HealthAccepted(pydantic.BaseModel):
    status: str = "ok"
