"""Контрактные тесты ingestion API (чек-лист дня 2 плана)."""

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from tests.conftest import auth_headers, load_fixture

if TYPE_CHECKING:
    from src.bootstrap import Container

async def fetch_scalar(app: FastAPI, sql: str) -> object:
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        return await conn.scalar(text(sql))


async def fetch_row(app: FastAPI, sql: str) -> tuple[object, ...]:
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        result = await conn.execute(text(sql))
        row = result.first()
        return tuple(row) if row is not None else ()


class TestAuth:
    async def test_missing_token_rejected_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/telemetry", json=load_fixture("telemetry-valid.json"))
        assert response.status_code == 401

    async def test_wrong_scheme_rejected_401(self, client: AsyncClient) -> None:
        # Агент шлёт ровно "Bearer <token>" — другая схема не допускается.
        response = await client.post(
            "/api/v1/telemetry",
            json=load_fixture("telemetry-valid.json"),
            headers={"Authorization": "Token abc"},
        )
        assert response.status_code == 401

    async def test_wrong_token_rejected_403(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/telemetry",
            json=load_fixture("telemetry-valid.json"),
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 403


@pytest.mark.usefixtures("clean_database")
class TestTelemetry:
    async def test_valid_batch_persists(self, client: AsyncClient, app: FastAPI) -> None:
        fixture = load_fixture("telemetry-valid.json")

        response = await client.post("/api/v1/telemetry", json=fixture, headers=auth_headers(app))

        assert response.status_code == 200
        assert response.json() == {"received": 1, "inserted": 1, "duplicates": 0}
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM beam_readings") == 64
        assert await fetch_scalar(app, "SELECT count(*) FROM buildup_zones") == 8
        assert (
            await fetch_scalar(app, "SELECT DISTINCT algorithm_version FROM buildup_zones")
        ) == "radial-slope-v1"

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
        # Edge шлёт метры: луч 0 (DistanceNotUpdating) исключается;
        # луч 63 (HeightSimulated) остаётся → max=99.5, min=2.01.
        fixture = load_fixture("telemetry-valid.json")

        await client.post("/api/v1/telemetry", json=fixture, headers=auth_headers(app))

        min_level = await fetch_scalar(app, "SELECT min_level FROM measurements")
        max_level = await fetch_scalar(app, "SELECT max_level FROM measurements")
        assert min_level == pytest.approx(2.01)
        assert max_level == pytest.approx(99.5)

    async def test_duplicate_does_not_insert_twice(self, client: AsyncClient, app: FastAPI) -> None:
        headers = auth_headers(app)
        valid = load_fixture("telemetry-valid.json")
        duplicate = load_fixture("telemetry-duplicate.json")
        duplicate["packets"][0]["ts"] = "2026-08-25T10:01:00Z"

        first = await client.post("/api/v1/telemetry", json=valid, headers=headers)
        second = await client.post("/api/v1/telemetry", json=duplicate, headers=headers)

        assert first.status_code == 200
        # Повтор принятого пакета — тоже успех, но без вставки (контракт edge).
        assert second.status_code == 200
        assert second.json()["duplicates"] == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM ingest_ledger") == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM beam_readings") == 64
        assert await fetch_scalar(app, "SELECT count(*) FROM buildup_zones") == 8

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
        assert await fetch_scalar(app, "SELECT count(*) FROM buildup_zones") == 0

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

    async def test_telemetry_touch_keeps_node_online(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        """Холодный старт: телеметрия без /health всё равно оживляет узел."""
        container: Container = app.state.container
        async with container.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO bunkers (id, name) VALUES ('bunker-1', 'Бункер №1') "
                    "ON CONFLICT DO NOTHING"
                )
            )

        response = await client.post(
            "/api/v1/telemetry",
            json=load_fixture("telemetry-valid.json"),
            headers=auth_headers(app),
        )

        assert response.status_code == 200
        node_id, online = await fetch_row(
            app, "SELECT node_id, last_seen_at >= now() - interval '2 seconds' FROM edge_nodes"
        )
        assert node_id == "bunker-1"
        assert online is True


@pytest.mark.usefixtures("clean_database")
class TestUnknownBunker:
    async def test_unknown_bunker_is_registered(self, client: AsyncClient, app: FastAPI) -> None:
        fixture = load_fixture("telemetry-valid.json")
        fixture["bunker_id"] = "bunker-missing"

        response = await client.post(
            "/api/v1/telemetry", json=fixture, headers=auth_headers(app)
        )

        assert response.status_code == 200
        assert await fetch_scalar(
            app, "SELECT name FROM bunkers WHERE id = 'bunker-missing'"
        ) == "bunker-missing"
        assert await fetch_scalar(
            app, "SELECT count(*) FROM geometries WHERE bunker_id = 'bunker-missing'"
        ) == 1
        assert await fetch_scalar(app, "SELECT count(*) FROM measurements") == 1

        listed = await client.get("/api/v1/bunkers")
        assert listed.status_code == 200
        assert any(item["id"] == "bunker-missing" for item in listed.json())


@pytest.mark.usefixtures("clean_database")
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


@pytest.mark.usefixtures("clean_database")
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

    async def test_events_touch_node(self, client: AsyncClient, app: FastAPI) -> None:
        """Каждый POST продлевает last_seen_at (dead-man, блок F плана)."""
        container: Container = app.state.container
        async with container.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO bunkers (id, name) VALUES ('bunker-1', 'Бункер №1') "
                    "ON CONFLICT DO NOTHING"
                )
            )

        response = await client.post(
            "/api/v1/events",
            json=load_fixture("events-valid.json"),
            headers=auth_headers(app),
        )

        assert response.status_code == 200
        node_id, online = await fetch_row(
            app, "SELECT node_id, last_seen_at >= now() - interval '2 seconds' FROM edge_nodes"
        )
        assert node_id == "bunker-1"
        assert online is True

    async def test_quarantined_payload_validated(self, client: AsyncClient, app: FastAPI) -> None:
        """payload жёстко типизирован и связан с type (контракт EdgePC)."""
        fixture = load_fixture("events-valid.json")
        # Правильная пара тип/payload проходит.
        fixture["events"].append(
            {
                "event_id": "9b2f0d47-a111-4f02-9d3e-6f5c8b9012ae",
                "ts": "2026-08-25T10:01:00Z",
                "type": "packet_quarantined",
                "payload": {
                    "telemetry_packet_id": 42,
                    "telemetry_packet_event_id": "3f9d51ac-6c33-4a52-b37a-9f2f4d0e5b71",
                    "attempts": 3,
                },
            }
        )

        ok = await client.post("/api/v1/events", json=fixture, headers=auth_headers(app))

        # Несоответствие payload типу отвергается целиком.
        fixture["events"][0]["type"] = "radar_recovered"  # payload от radar_down

        bad = await client.post("/api/v1/events", json=fixture, headers=auth_headers(app))

        assert ok.status_code == 200
        assert bad.status_code == 422

    async def test_unknown_event_type_rejected(self, client: AsyncClient, app: FastAPI) -> None:
        fixture = load_fixture("events-valid.json")
        fixture["events"][0]["type"] = "mystery_event"

        response = await client.post("/api/v1/events", json=fixture, headers=auth_headers(app))

        assert response.status_code == 422
        assert await fetch_scalar(app, "SELECT count(*) FROM edge_events") == 0


@pytest.mark.usefixtures("clean_database")
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
        # Непрозрачный bunker_id служит идентичностью узла.
        node_id, cpu = await fetch_row(app, "SELECT node_id, cpu FROM edge_nodes")
        assert node_id == "bunker-1"
        assert cpu == pytest.approx(37.5)
        workers_json = await fetch_scalar(app, "SELECT workers::text FROM edge_nodes")
        assert isinstance(workers_json, str) and '"dispatch"' in workers_json
        pending = await fetch_scalar(app, "SELECT pending_count FROM edge_nodes")
        assert pending == 3

        # Повторный снимок обновляет строку, а не добавляет новую.
        fixture["cpu_percent"] = 44.0
        second = await client.post("/api/v1/health", json=fixture, headers=headers)
        assert second.status_code == 200
        assert await fetch_scalar(app, "SELECT count(*) FROM edge_nodes") == 1
        cpu_after = await fetch_scalar(app, "SELECT cpu FROM edge_nodes")
        assert cpu_after == pytest.approx(44.0)

    async def test_health_rejects_legacy_contract(self, client: AsyncClient, app: FastAPI) -> None:
        """Старое тело (node_id/cpu/edge_time) больше не контракт — 422."""
        container: Container = app.state.container
        async with container.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO bunkers (id, name) VALUES ('bunker-1', 'Бункер №1') "
                    "ON CONFLICT DO NOTHING"
                )
            )

        response = await client.post(
            "/api/v1/health",
            json={
                "node_id": "edge-01",
                "bunker_id": "bunker-1",
                "cpu": 37.5,
                "ram": 62.0,
                "disk": 71.25,
                "edge_time": "2026-08-25T10:00:05Z",
            },
            headers=auth_headers(app),
        )

        assert response.status_code == 422
