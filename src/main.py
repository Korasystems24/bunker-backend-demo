"""Точка входа FastAPI: app factory + lifespan."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import loguru
from fastapi import FastAPI

from src import __version__
from src.api.ops import router as ops_router
from src.bootstrap import Container, build_container
from src.config.settings import Settings, get_settings
from src.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: Container = app.state.container
    loguru.logger.info("Bunker backend запущен (v{})", __version__)
    yield
    await container.engine.dispose()
    loguru.logger.info("Bunker backend остановлен, пул соединений закрыт")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(level=settings.logging.level, json_logs=settings.logging.json_logs)
    container = build_container(settings)

    app = FastAPI(
        title="Bunker Backend",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.container = container
    app.include_router(ops_router)
    return app


app = create_app()
