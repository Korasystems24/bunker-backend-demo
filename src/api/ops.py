"""Служебные (ops) эндпоинты без префикса /api/v1."""

from fastapi import APIRouter
from sqlalchemy import text

from src import __version__
from src.api.deps import ContainerDep
from src.api.schemas.health import HealthzResponse

router = APIRouter(tags=["ops"])


@router.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    """Liveness самого процесса API; к БД не ходит (это не /api/v1/health)."""
    return HealthzResponse(status="ok", version=__version__)


@router.get("/readyz", response_model=HealthzResponse)
async def readyz(container: ContainerDep) -> HealthzResponse:
    """Readiness: процесс жив и БД отвечает."""
    async with container.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return HealthzResponse(status="ok", version=__version__)
