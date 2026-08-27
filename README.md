# backend — приём телеметрии EdgePC, TimescaleDB, Query API для фронта

Серверная часть системы мониторинга бункеров: агент сам доставляет пакеты
(at-least-once), сервер гасит дубли и отдаёт фронту временные ряды.

## Стек

Python 3.12 · FastAPI · SQLAlchemy 2.x (async) · asyncpg · Alembic ·
pydantic-settings · loguru · TimescaleDB (pg16) · Docker Compose · ruff + basedpyright.

## Структура

```text
src/
├── main.py                  # app factory + lifespan + CORS/gzip/request-id
├── bootstrap.py             # composition root
├── config/settings.py       # pydantic-settings, секции BUNKER_*
├── api/
│   ├── ops.py               # GET /healthz, /readyz
│   ├── middleware.py        # X-Request-ID
│   └── v1/                  # ingest + query
├── application/             # ingestion, query, buildup, silence
├── domain/
└── infrastructure/database/
scripts/seed_catalog.py      # справочник bunkers + geometries
alembic/versions/
docker/
```

## Быстрый старт (локально)

```bash
uv sync
docker compose up -d db
cp .env.example .env
uv run alembic upgrade head
uv run python scripts/seed_catalog.py
uv run uvicorn src.main:app --reload
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

Деплой на Ubuntu с публичным IP — [DEPLOY.md](DEPLOY.md).

## Docker

```bash
docker compose up --build
```

Postgres снаружи слушает только `127.0.0.1`. API — порт `8000`.

## Конфигурация

Переменные `BUNKER_*`, вложенность через `__`, см. `.env.example`.

## Query API

```text
GET /api/v1/bunkers
GET /api/v1/bunkers/:id/geometry
GET /api/v1/bunkers/:id/measurements/latest
GET /api/v1/bunkers/:id/measurements?from&to&limit&offset
GET /api/v1/bunkers/:id/stats?period=day|week|month
GET /api/v1/bunkers/:id/buildup
GET /api/v1/health
```

Списочные ручки не отдают `beams`. `limit` ≤ 100. Графики — только серверные
часовые бакеты. Ошибки: `{"error": "..."}` — `"Bunker not found"`,
`"No measurements"`, `"No data"`.

## Ingestion API (EdgePC)

| Переменная EdgePC | Значение |
| --- | --- |
| `DISPATCH__HTTP__SERVER_URL` | `http://<host>:8000/api/v1` |
| `DISPATCH__HTTP__AUTH_TOKEN` | = `BUNKER_API__EDGE_AUTH_TOKEN` |

`POST /telemetry`, `/events`, `/health` с `Authorization: Bearer`. `200` — успех
включая дубль; `401`/`403` — токен; `422` — батч целиком (в том числе неизвестный
`bunker_id`); `5xx` — ретрай. Уровни и высоты лучей приходят в миллиметрах,
в хранилище и Query API — метры. `node_id` агент не шлёт (`bunker-1` → `edge-1`).

Справочник бункеров обязан существовать до первого пакета:

```bash
uv run python scripts/seed_catalog.py
```
