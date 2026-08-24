"""Служебные (ops) эндпоинты без префикса /api/v1."""

from fastapi import APIRouter

from src import __version__
from src.api.schemas.health import HealthzResponse

router = APIRouter(tags=["ops"])


@router.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    """Liveness самого процесса API; к БД не ходит (это не /api/v1/health)."""
    return HealthzResponse(status="ok", version=__version__)
