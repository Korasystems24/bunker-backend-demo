"""Контрактные тесты ingestion API (чек-лист дня 2 плана)."""

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from tests.conftest import auth_headers, load_fixture

if TYPE_CHECKING:
    from src.bootstrap import Container

pytestmark = pytest.mark.usefixtures("clean_database")


async def fetch_scalar(app: FastAPI, sql: str) -> object:
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        return await conn.scalar(text(sql))


class TestAuth:
    async def test_missing_api_key_rejected_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/telemetry", json=load_fixture("telemetry-valid.json"))
        assert response.status_code == 401

    async def test_wrong_api_key_rejected_403(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/telemetry",
            json=load_fixture("telemetry-valid.json"),
            headers={"X-API-Key": "wrong-token"},
        )
        assert response.status_code == 403


class TestTelemetry:
    async def test_valid_batch_persists(self, client: AsyncClient, app: FastAPI) -> None:
        fixture = load_fixture("telemetry-valid.json")

        response = await client.post("/api/v1/telemetry", json=fixture, headers=auth_headers(app))

        assert response.status_code == 200
        assert response.json() == {"received": 1, "inserted": 1, "duplicates": 0}
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM beam_readings") == 64

        # Имена лучов выводятся из позиции; флаги складываются в строку.
        a1_flags = await fetch_scalar(
            app, "SELECT beam_flags FROM beam_readings WHERE beam_name = 'A1'"
        )
        assert a1_flags == "DistanceNotUpdating"
        reliable_flags = await fetch_scalar(
            app, "SELECT beam_flags FROM beam_readings WHERE beam_name = 'A2'"
        )
        assert reliable_flags == ""
        h8_flags = await fetch_scalar(
            app,
            "SELECT beam_flags FROM beam_readings WHERE beam_name = 'H8'",
        )
        assert h8_flags == "HeightSimulated"

    async def test_min_max_computed_on_ingest(self, client: AsyncClient, app: FastAPI) -> None:
        # Луч 0 (DistanceNotUpdating) и луч 63 (HeightSimulated) исключаются:
        # min=2.01 (луч 1), max=2.41 (луч 62).
        fixture = load_fixture("telemetry-valid.json")

        await client.post("/api/v1/telemetry", json=fixture, headers=auth_headers(app))

        min_level = await fetch_scalar(app, "SELECT min_level FROM measurements")
        max_level = await fetch_scalar(app, "SELECT max_level FROM measurements")
        assert min_level == pytest.approx(2.01)
        assert max_level == pytest.approx(2.41)

    async def test_duplicate_does_not_insert_twice(self, client: AsyncClient, app: FastAPI) -> None:
        headers = auth_headers(app)
        valid = load_fixture("telemetry-valid.json")
        duplicate = load_fixture("telemetry-duplicate.json")

        first = await client.post("/api/v1/telemetry", json=valid, headers=headers)
        second = await client.post("/api/v1/telemetry", json=duplicate, headers=headers)

        assert first.status_code == 200
        # Повтор принятого пакета — тоже успех, но без вставки (контракт edge).
        assert second.status_code == 200
        assert second.json()["duplicates"] == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM beam_readings") == 64

    async def test_invalid_batch_rejected_without_writes(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        # 63 луча вместо 64 — нарушение контракта.
        response = await client.post(
            "/api/v1/telemetry",
            json=load_fixture("telemetry-invalid.json"),
            headers=auth_headers(app),
        )

        assert response.status_code == 422
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 0
        assert await fetch_scalar(app, "SELECT count(*) FROM beam_readings") == 0

    async def test_mixed_batch_is_all_or_nothing(self, client: AsyncClient, app: FastAPI) -> None:
        # Второй пакет батча невалиден → первый (валидный) тоже не пишется.
        fixture = load_fixture("telemetry-valid.json")
        broken = dict(fixture["packets"][0])
        broken["mass"] = -5.0  # mass >= 0 по контракту
        broken["event_id"] = "11111111-2222-4333-8444-555555555555"
        fixture["packets"].append(broken)

        response = await client.post("/api/v1/telemetry", json=fixture, headers=auth_headers(app))

        assert response.status_code == 422
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 0


class TestNoDataTelemetry:
    """Перебой питания лидара: лучи NotUsed, величины не посчитаны."""

    async def test_all_not_used_stored_with_nulls(self, client: AsyncClient, app: FastAPI) -> None:
        fixture = load_fixture("telemetry-all-not-used.json")

        response = await client.post("/api/v1/telemetry", json=fixture, headers=auth_headers(app))

        assert response.status_code == 200
        assert response.json()["inserted"] == 1

        # Измерение сохранено как «точка без данных», а не отброшено.
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM beam_readings") == 64
        for column in ("avg_level", "min_level", "max_level", "mass", "volume"):
            value = await fetch_scalar(app, f"SELECT {column} FROM measurements")
            assert value is None
        not_used_count = await fetch_scalar(
            app,
            "SELECT count(*) FROM beam_readings WHERE beam_flags = 'NotUsed'",
        )
        assert not_used_count == 64


class TestEvents:
    async def test_events_saved_and_deduplicated(self, client: AsyncClient, app: FastAPI) -> None:
        headers = auth_headers(app)
        fixture = load_fixture("events-valid.json")

        first = await client.post("/api/v1/events", json=fixture, headers=headers)
        second = await client.post("/api/v1/events", json=fixture, headers=headers)

        assert first.status_code == 200
        assert first.json() == {"received": 1, "inserted": 1, "duplicates": 0}
        assert second.status_code == 200
        assert second.json()["duplicates"] == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM edge_events") == 1

    async def test_unknown_event_type_rejected(self, client: AsyncClient, app: FastAPI) -> None:
        fixture = load_fixture("events-valid.json")
        fixture["events"][0]["type"] = "mystery_event"

        response = await client.post("/api/v1/events", json=fixture, headers=auth_headers(app))

        assert response.status_code == 422
        assert await fetch_scalar(app, "SELECT count(*) FROM edge_events") == 0


class TestHealth:
    async def test_health_upserts_edge_node(self, client: AsyncClient, app: FastAPI) -> None:
        # Справочник бункеров заполняется сидом/конфигуратором до старта edge.
        container: Container = app.state.container
        async with container.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO bunkers (id, name) VALUES ('bunker-1', 'Бункер №1') "
                    "ON CONFLICT DO NOTHING"
                )
            )

        headers = auth_headers(app)
        fixture = load_fixture("health-valid.json")

        first = await client.post("/api/v1/health", json=fixture, headers=headers)
        assert first.status_code == 200
        assert first.json() == {"status": "ok"}
        assert await fetch_scalar(app, "SELECT count(*) FROM edge_nodes") == 1
        cpu = await fetch_scalar(app, "SELECT cpu FROM edge_nodes")
        assert cpu == pytest.approx(37.5)

        # Повторный снимок обновляет строку, а не добавляет новую.
        fixture["cpu"] = 44.0
        second = await client.post("/api/v1/health", json=fixture, headers=headers)
        assert second.status_code == 200
        assert await fetch_scalar(app, "SELECT count(*) FROM edge_nodes") == 1
        cpu_after = await fetch_scalar(app, "SELECT cpu FROM edge_nodes")
        assert cpu_after == pytest.approx(44.0)
