"""Сущность: последнее известное состояние узла edge (для GET /api/v1/health)."""

import pydantic

from src.domain.value_objects.types import Timestamp


class EdgeNodeState(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    node_id: str
    bunker_id: str | None = None
    online: bool
    last_seen_at: Timestamp | None = None
    cpu: float | None = None
    ram: float | None = None
    disk: float | None = None
