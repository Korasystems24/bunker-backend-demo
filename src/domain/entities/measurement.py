"""Сущность: измерение бункера в момент ts (строка measurements)."""

import uuid

import pydantic

from src.domain.value_objects.types import Timestamp


class Measurement(pydantic.BaseModel):
    """min/max считаются на ингесте по надёжным лучам, не на чтении.

    id — монотонный числовой row-id из БД; при записи
    присваивается триггером, поэтому в ingest-пути равен None.
    """

    model_config = pydantic.ConfigDict(frozen=True)

    id: int | None = None
    event_id: uuid.UUID
    ts: Timestamp
    avg_level: float | None = None
    min_level: float | None = None
    max_level: float | None = None
    volume: float | None = None
    mass: float | None = None
