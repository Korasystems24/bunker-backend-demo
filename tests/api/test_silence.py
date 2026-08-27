"""Сценарий дня 4: остановил edge → offline + alert → запустил → online."""

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from tests.api.test_query import seed_bunkers, seed_online_node
from tests.conftest import auth_headers, load_fixture

if TYPE_CHECKING:
    from src.bootstrap import Container

pytestmark = pytest.mark.usefixtures("clean_query_database")


async def fetch_scalar(app: FastAPI, sql: str) -> object:
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        return await conn.scalar(text(sql))


class TestSilenceMonitor:
    async def test_stale_node_goes_offline_then_recovers(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        await seed_bunkers(app)
        await seed_online_node(app, age_sec=3600)

        # GET не ждёт тик монитора: online считается по свежести last_seen_at.
        listed = await client.get("/api/v1/bunkers")
        assert listed.json()[0]["online"] is False

        await app.state.container.silence.tick()

        status = await fetch_scalar(app, "SELECT status FROM edge_nodes WHERE node_id = 'edge-1'")
        assert status == "offline"
        open_alerts = await fetch_scalar(
            app,
            "SELECT count(*) FROM alerts "
            "WHERE node_id = 'edge-1' AND type = 'silence_started' AND resolved_at IS NULL",
        )
        assert open_alerts == 1

        health = load_fixture("health-valid.json")
        recovered = await client.post("/api/v1/health", json=health, headers=auth_headers(app))
        assert recovered.status_code == 200

        status = await fetch_scalar(app, "SELECT status FROM edge_nodes WHERE node_id = 'edge-1'")
        assert status == "online"
        still_open = await fetch_scalar(
            app,
            "SELECT count(*) FROM alerts "
            "WHERE node_id = 'edge-1' AND type = 'silence_started' AND resolved_at IS NULL",
        )
        assert still_open == 0
        resolved_events = await fetch_scalar(
            app,
            "SELECT count(*) FROM alerts WHERE node_id = 'edge-1' AND type = 'silence_resolved'",
        )
        assert resolved_events == 1

        listed = await client.get("/api/v1/bunkers")
        assert listed.json()[0]["online"] is True
        health_body = await client.get("/api/v1/health")
        assert health_body.json()["edge_pcs"][0]["online"] is True

    async def test_never_seen_node_has_no_silence_alert(self, app: FastAPI) -> None:
        """«Никогда не подключался» ≠ «пропал»: без last_seen_at алерта нет."""
        await seed_bunkers(app)
        container: Container = app.state.container
        async with container.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO edge_nodes (node_id, bunker_id, status) "
                    "VALUES ('edge-1', 'bunker-1', 'unknown')"
                )
            )

        await app.state.container.silence.tick()

        status = await fetch_scalar(app, "SELECT status FROM edge_nodes WHERE node_id = 'edge-1'")
        assert status == "unknown"
        alerts = await fetch_scalar(app, "SELECT count(*) FROM alerts")
        assert alerts == 0

    async def test_tick_is_idempotent_while_still_silent(self, app: FastAPI) -> None:
        await seed_bunkers(app)
        await seed_online_node(app, age_sec=3600)

        await app.state.container.silence.tick()
        await app.state.container.silence.tick()

        started = await fetch_scalar(
            app,
            "SELECT count(*) FROM alerts WHERE type = 'silence_started'",
        )
        assert started == 1
