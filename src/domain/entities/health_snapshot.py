"""Снимок состояния edge-узла (POST /health; история не хранится)."""

import pydantic

from src.domain.value_objects.types import Timestamp


class HealthSnapshot(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    node_id: str
    bunker_id: str
    cpu: float = pydantic.Field(ge=0, le=100)
    ram: float = pydantic.Field(ge=0, le=100)
    disk: float = pydantic.Field(ge=0, le=100)
    edge_time: Timestamp
