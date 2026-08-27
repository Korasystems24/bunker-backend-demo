"""Точка входа FastAPI: app factory + lifespan."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

import loguru
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src import __version__
from src.api.errors import register_error_handlers
from src.api.middleware import RequestIdMiddleware
from src.api.ops import router as ops_router
from src.api.v1.buildup import router as buildup_router
from src.api.v1.bunkers import router as bunkers_router
from src.api.v1.health import router as edge_health_router
from src.api.v1.ingest import router as ingest_router
from src.api.v1.stats import router as stats_router
from src.bootstrap import Container, build_container
from src.config.settings import Settings, get_settings
from src.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: Container = app.state.container
    monitor_task = asyncio.create_task(container.silence.run(), name="silence-monitor")
    loguru.logger.info("Bunker backend запущен (v{})", __version__)
    try:
        yield
    finally:
        monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task
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

    # Порядок важен: последний добавленный middleware — внешний.
    # Request-id снаружи, GZip внутри CORS — сжатые ответы несут CORS-заголовки.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "ETag"],
    )
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)

    app.include_router(ops_router)
    app.include_router(ingest_router)
    app.include_router(bunkers_router)
    app.include_router(stats_router)
    app.include_router(buildup_router)
    app.include_router(edge_health_router)
    return app


app = create_app()
