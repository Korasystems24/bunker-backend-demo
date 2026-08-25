"""Сущность: событие edge (строка edge_events, дедуп по PK).

Тип и payload связаны валидатором так же, как на EdgePC (PAYLOAD_BY_TYPE):
каждому типу соответствует ровно одна модель payload.
"""

import uuid
from typing import Self

import pydantic

from src.domain.value_objects.event_payload import (
    PacketQuarantined,
    RadarDown,
    RadarRecovered,
    WorkerFatal,
    WorkerRestarted,
)
from src.domain.value_objects.types import EdgeEventPayload, EventType, Timestamp

PAYLOAD_BY_TYPE: dict[EventType, type[EdgeEventPayload]] = {
    "radar_down": RadarDown,
    "radar_recovered": RadarRecovered,
    "packet_quarantined": PacketQuarantined,
    "worker_restarted": WorkerRestarted,
    "fatal_error": WorkerFatal,
}


class EdgeEvent(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    event_id: uuid.UUID
    ts: Timestamp
    type: EventType
    payload: EdgeEventPayload

    @pydantic.model_validator(mode="after")
    def _payload_matches_type(self) -> Self:
        expected = PAYLOAD_BY_TYPE[self.type]
        if type(self.payload) is not expected:
            raise ValueError(
                f"{self.type} ожидает {expected.__name__}, "
                f"получен {type(self.payload).__name__}"
            )
        return self
