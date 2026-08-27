"""Проверяется форма ответов Query API, отсутствие beams в списках,
серверная агрегация stats, ETag/304 на геометрии, gzip/CORS, формат ошибок.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from tests.conftest import auth_headers, refresh_hourly_cagg

if TYPE_CHECKING:
    from src.bootstrap import Container

pytestmark = pytest.mark.usefixtures("clean_query_database")

MINIMAL_GEOMETRY: dict[str, Any] = {
    "shape": {"type": "truncated_cone", "height_m": 8.0},
    "sensor": {"x": 0, "y": 0, "z": 8.5, "tilt_deg": 0},
    "beams": [{"beam_name": "A1", "axis": "A", "position": 1, "x": 0.35, "y": 0.0, "z": 0}],
}


async def run_sql(
    app: FastAPI, sql: str, params: dict[str, Any] | list[dict[str, Any]] | None = None
) -> Any:
    """Выполняет SQL от имени теста (прямой контроль данных, минуя ingestion)."""
    container: Container = app.state.container
    async with container.engine.begin() as conn:
        if isinstance(params, list):
            # executemany: результат без строк.
            await conn.execute(text(sql), params)
            return None
        result = await conn.execute(text(sql), params or {})
        return result.scalar() if result.returns_rows else None


async def seed_bunkers(app: FastAPI) -> None:
    await run_sql(
        app,
        "INSERT INTO bunkers (id, name) VALUES (:id, :name)",
        [{"id": "bunker-1", "name": "Бункер №1"}, {"id": "bunker-2", "name": "Бункер №2"}],
    )
    await run_sql(
        app,
        """
        INSERT INTO geometries (bunker_id, shape, sensor, beams)
        VALUES ('bunker-1', CAST(:shape AS jsonb), CAST(:sensor AS jsonb), CAST(:beams AS jsonb))
        """,
        {
            "shape": json.dumps(MINIMAL_GEOMETRY["shape"]),
            "sensor": json.dumps(MINIMAL_GEOMETRY["sensor"]),
            "beams": json.dumps(MINIMAL_GEOMETRY["beams"]),
        },
    )


async def seed_online_node(app: FastAPI, *, node_id: str = "edge-1", age_sec: int = 10) -> None:
    await run_sql(
        app,
        """
        INSERT INTO edge_nodes (node_id, bunker_id, last_seen_at, cpu, ram, disk, status)
        VALUES (:node_id, 'bunker-1', now() - make_interval(secs => :age),
                37.5, 50.0, 60.0, 'online')
        """,
        {"node_id": node_id, "age": age_sec},
    )


async def insert_measurement(
    app: FastAPI,
    bunker_id: str,
    ts: datetime,
    *,
    avg_level: float | None = None,
    beams: list[tuple[str, float, str]] | None = None,
) -> int:
    measurement_id: Any = await run_sql(
        app,
        """
        INSERT INTO measurements (bunker_id, event_id, ts, avg_level)
        VALUES (:bunker_id, gen_random_uuid(), :ts, :avg_level)
        RETURNING id
        """,
        {"bunker_id": bunker_id, "ts": ts, "avg_level": avg_level},
    )
    if beams:
        await run_sql(
            app,
            """
            INSERT INTO beam_readings (bunker_id, ts, beam_name, height, beam_flags)
            SELECT :bunker_id, :ts, b.name, b.height, b.flags
            FROM unnest(CAST(:names AS text[]), CAST(:heights AS real[]), CAST(:flags AS text[]))
                 AS b(name, height, flags)
            """,
            {
                "bunker_id": bunker_id,
                "ts": ts,
                "names": [b[0] for b in beams],
                "heights": [b[1] for b in beams],
                "flags": [b[2] for b in beams],
            },
        )
    return int(measurement_id)


def hours_ago(hours: float) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


class TestBunkers:
    async def test_list_matches_query_contract(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        await seed_online_node(app)

        response = await client.get("/api/v1/bunkers")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": "bunker-1",
                "name": "Бункер №1",
                "online": True,
                "geometry_id": "geom-bunker-1",
            },
            {
                "id": "bunker-2",
                "name": "Бункер №2",
                "online": False,
                "geometry_id": "geom-bunker-2",
            },
        ]

    async def test_stale_node_is_offline(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        await seed_online_node(app, age_sec=3600)

        response = await client.get("/api/v1/bunkers")

        assert response.json()[0]["online"] is False


class TestGeometry:
    async def test_body_and_caching_headers(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)

        response = await client.get("/api/v1/bunkers/bunker-1/geometry")

        assert response.status_code == 200
        assert response.json() == {"bunker_id": "bunker-1", **MINIMAL_GEOMETRY}
        etag = response.headers["etag"]
        assert etag.startswith('"')
        assert "max-age=300" in response.headers["cache-control"]

        revalidated = await client.get(
            "/api/v1/bunkers/bunker-1/geometry", headers={"If-None-Match": etag}
        )
        assert revalidated.status_code == 304

    async def test_unknown_bunker_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/bunkers/nope/geometry")

        assert response.status_code == 404
        assert response.json() == {"error": "Bunker not found"}


class TestLatest:
    async def test_returns_measurement_with_beams(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        await insert_measurement(app, "bunker-1", hours_ago(1), avg_level=2.5)
        newer_id = await insert_measurement(
            app,
            "bunker-1",
            hours_ago(0.01),
            avg_level=2.6,
            beams=[("A1", 1.234567, "WeakSignal"), ("A2", 2.5, ""), ("H8", 0.0, "Disabled")],
        )

        response = await client.get("/api/v1/bunkers/bunker-1/measurements/latest")

        assert response.status_code == 200
        body = response.json()
        # Последнее измерение — по ts, не по порядку вставки.
        assert body["id"] == newer_id
        for key in ("avg_level", "min_level", "max_level", "volume", "mass"):
            assert key in body
        assert [b["beam_name"] for b in body["beams"]] == ["A1", "A2", "H8"]
        assert body["beams"][0] == {"beam_name": "A1", "height": 1.2346, "status": "WeakSignal"}
        assert body["beams"][1]["status"] == ""

    async def test_no_data_404(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)

        response = await client.get("/api/v1/bunkers/bunker-1/measurements/latest")

        assert response.status_code == 404
        assert response.json() == {"error": "No measurements"}


class TestMeasurementsPage:
    async def test_page_without_beams(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        for i in range(3):
            await insert_measurement(
                app,
                "bunker-1",
                hours_ago(3 - i),
                avg_level=1.0 + i,
                beams=[("A1", 1.0, "")],
            )

        response = await client.get(
            "/api/v1/bunkers/bunker-1/measurements", params={"limit": 2, "offset": 1}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["limit"] == 2
        assert body["offset"] == 1
        # Новые вперёд и БЕЗ ключа beams (защита фронта от лагов).
        assert [item["id"] for item in body["items"]] == sorted(
            (item["id"] for item in body["items"]), reverse=True
        )
        assert all("beams" not in item for item in body["items"])

    async def test_from_to_filters(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        base = datetime.now(UTC).replace(microsecond=0)
        for minutes in (180, 120, 60):
            await insert_measurement(app, "bunker-1", base - timedelta(minutes=minutes))

        response = await client.get(
            "/api/v1/bunkers/bunker-1/measurements",
            params={"from": (base - timedelta(minutes=150)).isoformat()},
        )

        assert response.json()["total"] == 2

        response = await client.get(
            "/api/v1/bunkers/bunker-1/measurements",
            params={
                "from": (base - timedelta(minutes=130)).isoformat(),
                "to": (base - timedelta(minutes=70)).isoformat(),
            },
        )
        assert response.json()["total"] == 1

    async def test_limit_clamped_server_side(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        await insert_measurement(app, "bunker-1", hours_ago(1))

        response = await client.get(
            "/api/v1/bunkers/bunker-1/measurements", params={"limit": 100000}
        )

        # Мок ограничивает страницу сотней (API.md), сервер — так же.
        assert response.json()["limit"] == 100


class TestStats:
    async def test_hourly_buckets_match_manual_math(
        self, client: AsyncClient, app: FastAPI
    ) -> None:
        await seed_bunkers(app)
        # Два измерения внутри одного часового бакета и одно в соседнем:
        # бакет 1: avg(1.0, 3.0) = 2.0; бакет 2: 5.0; общие min/max/avg по сырым строкам.
        anchor = (datetime.now(UTC) - timedelta(hours=2)).replace(minute=17, second=0)
        await insert_measurement(app, "bunker-1", anchor, avg_level=1.0)
        await insert_measurement(app, "bunker-1", anchor + timedelta(minutes=20), avg_level=3.0)
        await insert_measurement(app, "bunker-1", anchor + timedelta(hours=1), avg_level=5.0)
        await refresh_hourly_cagg(app)

        response = await client.get("/api/v1/bunkers/bunker-1/stats", params={"period": "day"})

        assert response.status_code == 200
        body = response.json()
        assert body["period"] == "day"
        assert body["min_level"] == pytest.approx(1.0)
        assert body["max_level"] == pytest.approx(5.0)
        assert body["avg_level"] == pytest.approx(3.0)
        assert len(body["series"]) == 2
        assert body["series"][0]["avg_level"] == pytest.approx(2.0)
        assert body["series"][1]["avg_level"] == pytest.approx(5.0)
        for point in body["series"]:
            for key in ("min_level", "max_level", "mass", "volume"):
                assert key in point

    async def test_periods_change_bucket_size(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        await insert_measurement(app, "bunker-1", hours_ago(1), avg_level=2.0)
        await insert_measurement(app, "bunker-1", hours_ago(25), avg_level=4.0)
        await insert_measurement(app, "bunker-1", hours_ago(24 * 29), avg_level=6.0)
        await refresh_hourly_cagg(app)

        week = await client.get("/api/v1/bunkers/bunker-1/stats", params={"period": "week"})
        month = await client.get("/api/v1/bunkers/bunker-1/stats", params={"period": "month"})
        day = await client.get("/api/v1/bunkers/bunker-1/stats", params={"period": "day"})

        # week (окно 7д): строки 1ч и 25ч → две часовые точки;
        # month (30д): все три; day (24ч): только свежая.
        assert len(week.json()["series"]) == 2
        assert len(month.json()["series"]) == 3
        assert len(day.json()["series"]) == 1

    async def test_empty_period_is_404(self, client: AsyncClient, app: FastAPI) -> None:
        """Данные старше горизонта периода не подставляются в график."""
        await seed_bunkers(app)
        for days in (31, 32, 33):
            await insert_measurement(
                app, "bunker-1", datetime.now(UTC) - timedelta(days=days), avg_level=2.0
            )
        await refresh_hourly_cagg(app)

        response = await client.get("/api/v1/bunkers/bunker-1/stats", params={"period": "day"})

        assert response.status_code == 404
        assert response.json() == {"error": "No data"}

    async def test_no_data_at_all_404(self, client: AsyncClient, app: FastAPI) -> None:
        """Совсем без измерений — 404 {"error": "No data"}."""
        await seed_bunkers(app)

        response = await client.get("/api/v1/bunkers/bunker-1/stats", params={"period": "day"})

        assert response.status_code == 404
        assert response.json() == {"error": "No data"}

    async def test_stats_unknown_bunker_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/bunkers/nope/stats", params={"period": "day"})

        assert response.status_code == 404
        assert response.json() == {"error": "Bunker not found"}


class TestEdgeHealth:
    async def test_edge_pcs_contract(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        await seed_online_node(app)

        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        (pc,) = response.json()["edge_pcs"]
        assert pc["node_id"] == "edge-1"
        assert pc["online"] is True
        assert pc["last_pulse"] is not None
        assert pc["cpu"] == pytest.approx(37.5)


class TestHttpBehavior:
    async def test_large_response_is_gzipped(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        for i in range(80):
            await insert_measurement(app, "bunker-1", hours_ago(80 - i), avg_level=1.0 + i / 10)

        response = await client.get(
            "/api/v1/bunkers/bunker-1/measurements", params={"limit": 80}
        )

        assert response.status_code == 200
        assert response.headers["content-encoding"] == "gzip"

    async def test_cors_allows_whitelisted_origin_only(self, client: AsyncClient) -> None:
        allowed = await client.get(
            "/api/v1/bunkers", headers={"Origin": "http://localhost:5173"}
        )
        denied = await client.get("/api/v1/bunkers", headers={"Origin": "http://evil.example"})

        assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-origin" not in denied.headers

    async def test_readyz_and_request_id(self, client: AsyncClient) -> None:
        response = await client.get("/readyz")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.headers["x-request-id"]

    async def test_errors_use_error_format(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/nope")

        assert response.status_code == 404
        assert response.json() == {"error": "Not Found"}

    async def test_invalid_query_params_rejected_with_error_format(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(
            "/api/v1/bunkers/bunker-1/measurements", params={"offset": -5}
        )

        assert response.status_code == 422
        assert set(response.json()) == {"error"}


class TestBuildup:
    async def test_zones_contract_and_math(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)
        # Ось A — ровный склон; ось B — внешние позиции подняты над уклоном.
        # Compute-on-write: зоны появляются только через ingest.
        # POST — миллиметры (контракт EdgePC); GET /buildup — метры.
        heights_a = [(2.0 - 0.1 * (p - 1)) * 1000 for p in range(1, 9)]
        heights_b = [
            (2.0 - 0.1 * (p - 1) + (1.0 if p >= 6 else 0.0)) * 1000 for p in range(1, 9)
        ]
        beams: list[dict[str, Any]] = []
        for _axis, heights in (("A", heights_a), ("B", heights_b)):
            for height in heights:
                beams.append({"height": height, "raw_status": None, "status": []})
        for _axis in "CDEFGH":
            for _ in range(8):
                beams.append({"height": 2000.0, "raw_status": None, "status": []})
        payload = {
            "bunker_id": "bunker-1",
            "packets": [
                {
                    "event_id": str(uuid.uuid4()),
                    "ts": datetime.now(UTC).isoformat(),
                    "avg_level": 2000.0,
                    "mass": 10.0,
                    "volume": 5.0,
                    "beams": beams,
                }
            ],
        }

        ingested = await client.post(
            "/api/v1/telemetry", json=payload, headers=auth_headers(app)
        )
        assert ingested.status_code == 200

        response = await client.get("/api/v1/bunkers/bunker-1/buildup")

        assert response.status_code == 200
        body = response.json()
        assert body["bunker_id"] == "bunker-1"
        assert body["threshold_m"] == pytest.approx(0.35)
        assert body["algorithm_version"] == "radial-slope-v1"
        assert [z["axis"] for z in body["zones"]] == list("ABCDEFGH")
        by_axis = {z["axis"]: z for z in body["zones"]}
        assert by_axis["A"]["severity"] == "none"
        assert by_axis["B"]["severity"] == "high"
        assert sorted(by_axis["B"]["affected_positions"]) == [6, 7, 8]
        for zone in body["zones"]:
            assert set(zone) == {"axis", "severity", "score", "deviation_m", "affected_positions"}

    async def test_no_measurements_404(self, client: AsyncClient, app: FastAPI) -> None:
        await seed_bunkers(app)

        response = await client.get("/api/v1/bunkers/bunker-1/buildup")

        assert response.status_code == 404
        # Текст ошибки — как у stats ("No data"), не как у /latest.
        assert response.json() == {"error": "No data"}
