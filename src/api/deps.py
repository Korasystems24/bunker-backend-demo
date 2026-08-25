"""Зависимости FastAPI: контейнер приложения и проверка Bearer-токена edge.

Схема совпадает с отправкой агента (EdgePC http_gateway._headers):
заголовок `Authorization: Bearer <token>`. 401 — заголовка/схемы нет,
403 — токен неверный; оба статуса агент считает фатальной ошибкой
конфигурации и навсегда останавливает диспетчеризацию.
"""

import secrets
from typing import Annotated

import fastapi

from src.bootstrap import Container

_BEARER_SCHEME = "bearer"


def get_container(http_request: fastapi.Request) -> Container:
    container: Container = http_request.app.state.container
    return container


ContainerDep = Annotated[Container, fastapi.Depends(get_container)]


async def require_edge_token(
    http_request: fastapi.Request,
    authorization: Annotated[str | None, fastapi.Header()] = None,
) -> None:
    if authorization is None:
        raise fastapi.HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != _BEARER_SCHEME or not token:
        raise fastapi.HTTPException(
            status_code=401, detail="Expected Authorization: Bearer <token>"
        )
    expected = get_container(http_request).settings.api.edge_auth_token
    if not secrets.compare_digest(token, expected):
        raise fastapi.HTTPException(status_code=403, detail="Invalid token")
