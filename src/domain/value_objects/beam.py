"""Value object: одиночное измерение луча."""

from typing import Annotated

import pydantic

from src.domain.value_objects.beam_status import BeamStatus


class Beam(pydantic.BaseModel):
    """Высота может быть отрицательной (ниже опорной точки), но не NaN/Inf.

    beam_name в пакете отсутствует: имя выводится из позиции луча в списке
    (0 -> 'A1' ... 63 -> 'H8') при записи в beam_readings.
    """

    model_config = pydantic.ConfigDict(frozen=True)

    height: Annotated[float, pydantic.Field(allow_inf_nan=False)] | None
    raw_status: int | None
    status: tuple[BeamStatus, ...]
