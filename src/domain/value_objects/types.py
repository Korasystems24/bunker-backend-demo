"""Общие типы-алиасы домена (контракт edge, фаза 7а)."""

from typing import Annotated, Literal

import pydantic

from src.domain.constants import BEAM_COUNT
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.event_payload import (
    FatalError,
    PacketQuarantined,
    RadarDown,
    RadarRecovered,
    WorkerRestarted,
)

TelemetryBeams = Annotated[list[Beam], pydantic.Field(min_length=BEAM_COUNT, max_length=BEAM_COUNT)]

# Измеренная радаром величина (масса, объём, уровень):
# конечное неотрицательное число; отсутствие значения выражается None на поле.
Measurement = Annotated[float, pydantic.Field(ge=0, allow_inf_nan=False)]

type Timestamp = pydantic.AwareDatetime

type EdgeEventPayload = (
    RadarDown | RadarRecovered | PacketQuarantined | WorkerRestarted | FatalError
)

type EventType = Literal[
    "radar_down",
    "radar_recovered",
    "packet_quarantined",
    "worker_restarted",
    "fatal_error",
]
