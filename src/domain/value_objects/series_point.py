"""Value object: точка серверного бакета stats для графиков фронта."""

from typing import Annotated

import pydantic

from src.domain.value_objects.types import Timestamp

# Числа приходят из SQL-агрегатов, уже округленные;
# отсутствие данных в бакете выражается None (бакет не должен существовать,
# но схема допускает «пустые» величины как в measurements).
Rounded = Annotated[float | None, pydantic.Field(allow_inf_nan=False)]


class SeriesPoint(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    ts: Timestamp
    avg_level: Rounded = None
    min_level: Rounded = None
    max_level: Rounded = None
    mass: Rounded = None
    volume: Rounded = None
