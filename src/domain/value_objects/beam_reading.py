"""Value object: луч в ответе Query API."""

import pydantic


class BeamReading(pydantic.BaseModel):
    """status — строка флагов через ', ' ('' если флагов нет)."""

    model_config = pydantic.ConfigDict(frozen=True)

    beam_name: str
    height: float | None = None
    status: str = ""
