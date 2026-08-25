"""Value object: луч в ответе Query API (контракт мока 1:1)."""

import pydantic


class BeamReading(pydantic.BaseModel):
    """status — строка флагов через ', ' ('' для надёжного луча), как отдаёт мок."""

    model_config = pydantic.ConfigDict(frozen=True)

    beam_name: str
    height: float | None = None
    status: str = ""
