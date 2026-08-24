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
                "edge_events, edge_nodes, alerts"
            )
        )
    yield


def auth_headers(app: FastAPI) -> dict[str, str]:
    """Заголовок с дефолтным ключом из настроек (тесты не меняют .env)."""
    container: Container = app.state.container
    return {"X-API-Key": container.settings.api.edge_api_key}
