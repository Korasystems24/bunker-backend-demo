"""Зависимости FastAPI: контейнер приложения и проверка ключа edge."""

import secrets
from typing import Annotated

import fastapi

from src.bootstrap import Container


def get_container(http_request: fastapi.Request) -> Container:
    container: Container = http_request.app.state.container
    return container


ContainerDep = Annotated[Container, fastapi.Depends(get_container)]


async def require_edge_api_key(
    http_request: fastapi.Request,
    x_api_key: Annotated[str | None, fastapi.Header(alias="X-API-Key")] = None,
) -> None:
    expected = get_container(http_request).settings.api.edge_api_key
    if x_api_key is None:
        raise fastapi.HTTPException(status_code=401, detail="Missing X-API-Key header")
    if not secrets.compare_digest(x_api_key, expected):
        raise fastapi.HTTPException(status_code=403, detail="Invalid API key")
