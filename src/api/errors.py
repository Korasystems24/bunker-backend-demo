"""Единый формат ошибок API: {"error": "..."} — как у мока (план, блок H)."""

from typing import Any

import fastapi
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from src.domain.exceptions import DomainError, NotFoundError


def _error_body(message: object) -> dict[str, str]:
    return {"error": str(message)}


# Сигнатуры обработчиков согласованы с контрактом Starlette
# (обработчик принимает общий Exception и сужает тип сам).
async def handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return JSONResponse(
        _error_body(exc.detail),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def handle_validation_exception(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Компактная сводка первой ошибки: путь поля + причина.
    errors: list[dict[str, Any]] = list(exc.errors())
    first: dict[str, Any] = errors[0] if errors else {}
    raw_loc: tuple[Any, ...] = tuple(first.get("loc", ()))
    loc = ".".join(str(part) for part in raw_loc if part != "body")
    msg: str = str(first.get("msg", "invalid"))
    message = f"{loc}: {msg}" if loc else "Validation failed"
    return JSONResponse(_error_body(message), status_code=422)


async def handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = 404 if isinstance(exc, NotFoundError) else 400
    message = exc.message if isinstance(exc, NotFoundError) else str(exc)
    return JSONResponse(_error_body(message), status_code=status)


def register_error_handlers(app: fastapi.FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_exception)
    app.add_exception_handler(DomainError, handle_domain_error)
