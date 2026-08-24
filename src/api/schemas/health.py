"""DTO служебных health-эндпоинтов."""

import pydantic


class HealthzResponse(pydantic.BaseModel):
    """Ответ ``GET /healthz`` — liveness самого API.

    Не путать с бизнесовым ``GET /api/v1/health`` про состояние edge-узлов.
    """

    status: str = "ok"
    version: str
