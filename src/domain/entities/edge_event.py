"""Сущность: событие edge (строка edge_events, дедуп по PK)."""

import uuid
from typing import Any

import pydantic

from src.domain.value_objects.types import EventType, Timestamp


class EdgeEvent(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    event_id: uuid.UUID
    ts: Timestamp
    type: EventType
    payload: dict[str, Any] = pydantic.Field(default_factory=dict)
