"""Сущность: геометрия бункера (расчёт — на конфигураторе)."""

from typing import Any

import pydantic


class Geometry(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    bunker_id: str
    shape: dict[str, Any]
    sensor: dict[str, Any]
    beams: list[dict[str, Any]]
