"""Снимок состояния edge-узла (POST /health; история не хранится).

Байтовая копия контракта EdgePC (src/domain/entities/health_snapshot.py):
агент шлёт bunker_id рядом с полем (см. api/schemas/ingest.HealthRequest).
"""

import pydantic

from src.domain.value_objects.types import Timestamp
from src.domain.value_objects.worker_health import WorkerHealth


class HealthSnapshot(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    ts: Timestamp
    workers: dict[str, WorkerHealth]
    pending_count: int = pydantic.Field(ge=0)
    quarantined_count: int = pydantic.Field(ge=0)
    free_bytes: int = pydantic.Field(ge=0)
    storage_paused: bool
    cpu_percent: float = pydantic.Field(ge=0, le=100, allow_inf_nan=False)
    memory_percent: float = pydantic.Field(ge=0, le=100, allow_inf_nan=False)
    disk_percent: float = pydantic.Field(ge=0, le=100, allow_inf_nan=False)
