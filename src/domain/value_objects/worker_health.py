"""Здоровье воркеров edge (часть снимка POST /health; копия контракта EdgePC)."""

import pydantic

from src.domain.value_objects.types import Timestamp


class FatalError(pydantic.BaseModel):
    """Фатальная ошибка воркера внутри WorkerHealth (не путать с событием
    fatal_error — там payload шире, см. value_objects.event_payload.WorkerFatal)."""

    model_config = pydantic.ConfigDict(frozen=True)

    reason: str
    restartable: bool


class WorkerHealth(pydantic.BaseModel):
    """Срез одного воркера. Те же поля, что держит сам воркер на edge."""

    model_config = pydantic.ConfigDict(frozen=True)

    alive: bool
    last_error: str | None = None
    last_error_at: Timestamp | None = None
    fatal: FatalError | None = None
