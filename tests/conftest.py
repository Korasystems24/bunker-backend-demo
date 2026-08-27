"""Общие фикстуры контрактных тестов.

Интеграция с реальным Timescale из compose (localhost:5432): тесты гоняются
в одном event-loop вместе с приложением через asgi-lifespan.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from src.main import create_app

if TYPE_CHECKING:
    from src.bootstrap import Container

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    # Any сознательно: JSON-полезная нагрузка произвольной структуры.
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    # LifespanManager.app возвращает обёртку ASGI, поэтому отдаём исходный инстанс.
    application = create_app()
    async with LifespanManager(application):
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def clean_database(app: FastAPI) -> AsyncIterator[None]:
    """Подключается только там, где объявлен в usefixtures (api-тесты)."""
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE measurements, beam_readings, buildup_zones, "
                "edge_events, ingest_ledger, edge_nodes, alerts"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO bunkers (id, name) VALUES ('bunker-1', 'Бункер №1') "
                "ON CONFLICT DO NOTHING"
            )
        )
    await refresh_hourly_cagg(app)
    yield


@pytest_asyncio.fixture
async def clean_query_database(app: FastAPI) -> AsyncIterator[None]:
    """Полная очистка включая справочник бункеров (query-тесты сеют сами)."""
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE measurements, beam_readings, buildup_zones, edge_events, "
                "ingest_ledger, edge_nodes, alerts, geometries, bunkers CASCADE"
            )
        )
    await refresh_hourly_cagg(app)
    yield


def auth_headers(app: FastAPI) -> dict[str, str]:
    """Bearer-заголовок с дефолтным токеном из настроек (тесты не меняют .env)."""
    container: Container = app.state.container
    return {"Authorization": f"Bearer {container.settings.api.edge_auth_token}"}


async def refresh_hourly_cagg(app: FastAPI) -> None:
    """Синхронизирует measurements_hourly. CALL нельзя внутри транзакции."""
    container: Container = app.state.container
    connectable = container.engine.execution_options(isolation_level="AUTOCOMMIT")
    async with connectable.connect() as conn:
        await conn.execute(
            text("CALL refresh_continuous_aggregate('measurements_hourly', NULL, now())")
        )
