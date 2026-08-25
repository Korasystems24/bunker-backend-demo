"""Value object: результат агрегации stats за период (серия + общие экстремумы)."""

import pydantic

from src.domain.value_objects.series_point import SeriesPoint


class StatsSnapshot(pydantic.BaseModel):
    """Общие min/max/avg считаются по avg_level сырых измерений периода — так же,

    как в моке (allLevels), а не по бакетам серии.
    """

    model_config = pydantic.ConfigDict(frozen=True)

    min_level: float | None = None
    max_level: float | None = None
    avg_level: float | None = None
    series: list[SeriesPoint] = pydantic.Field(default_factory=list)
