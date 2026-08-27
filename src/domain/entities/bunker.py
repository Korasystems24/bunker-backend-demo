"""Сущность: бункер (справочник + вычисленный признак online)."""

import pydantic


class Bunker(pydantic.BaseModel):
    """online — производственная характеристика узла edge, а не свойство бункера;

    считается репозиторием по свежести last_seen_at (dead-man).
    """

    model_config = pydantic.ConfigDict(frozen=True)

    id: str
    name: str
    online: bool
