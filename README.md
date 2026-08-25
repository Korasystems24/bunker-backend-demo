# backend-demo — серверная часть системы мониторинга бункеров

Приём телеметрии от EdgePC-агента, хранение временных рядов в PostgreSQL +
TimescaleDB и Query API для фронтенда. Реализация плана `docs/backend-demo-plan.md`.

## Стек

Python 3.12 · FastAPI · SQLAlchemy 2.x (async) · asyncpg · Alembic ·
pydantic-settings · loguru · TimescaleDB (pg16) · Docker Compose · ruff + basedpyright.

## Структура

```text
src/
├── main.py                  # app factory + lifespan + CORS/gzip
├── bootstrap.py             # composition root (сборка зависимостей)
├── config/settings.py       # pydantic-settings, секции BUNKER_*
├── logging_config.py        # loguru (+ request_id extra)
├── api/
│   ├── ops.py               # GET /healthz (liveness самого API)
│   ├── errors.py            # единый формат ошибок {"error": "..."}
│   ├── schemas/             # DTO (ingest = контракт edge, query = контракт мока)
│   └── v1/
│       ├── ingest.py        # POST /telemetry /events /health (Authorization: Bearer)
│       ├── bunkers.py       # GET /bunkers, /geometry (ETag), /measurements[/latest]
│       ├── stats.py         # GET .../stats?period=day|week|month
│       ├── buildup.py       # GET .../buildup (эвристика v1, on-read)
│       └── health.py        # GET /api/v1/health (edge_pcs)
├── application/
│   ├── ingestion/           # IngestionService (write-контур)
│   └── query/               # QueryService (read-контур CQRS-lite)
├── domain/                  # сущности, VO, порты
└── infrastructure/database/
    ├── engine.py            # async engine + sessionmaker (asyncpg)
    ├── models/              # ORM ТОЛЬКО справочных таблиц (bunkers, geometries)
    └── repositories/        # Sql*-репозитории: ВЕСЬ тайм-серийный SQL здесь
scripts/seed_demo.py         # генератор истории ИЗ МОКА → COPY в БД
alembic/versions/            # схема: гипертаблицы, политики Timescale
docker/                      # entrypoint api, init SQL для БД
```

## Быстрый старт (локально)

```bash
uv sync                                        # зависимости + .venv
docker compose up -d db                        # PostgreSQL + TimescaleDB
cp .env.example .env                           # и заполнить значения
uv run alembic upgrade head                    # схема v1 + политики
uv run uvicorn src.main:app --reload           # http://localhost:8000
curl http://localhost:8000/healthz             # {"status":"ok",...}
```

## Быстрый старт (Docker)

```bash
docker compose up --build     # api сам применит миграции перед стартом
curl http://localhost:8000/healthz
```

Проверка Timescale:

```bash
docker compose exec db psql -U bunker -d bunker -c "\dx"
docker compose exec db psql -U bunker -d bunker \
  -c "SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables;"
```

## Конфигурация

Все настройки — через переменные окружения `BUNKER_*` (вложенность через `__`),
см. `.env.example`. Секреты в git не попадают.

## Статус (план работ)

- [x] Шаг 1 / День 1 — каркас и хранилище (compose, Alembic, healthz)
- [x] Шаг 2 / День 2 — Ingestion API (`/telemetry`, `/events`, `/health`), дедуп, Bearer-токен, контрактные тесты
- [x] Шаг 3 / День 3 — Query API для фронта, seed_demo, CORS/gzip
- [ ] Шаг 4 / День 4 — buildup v1, SilenceMonitor, continuous aggregates
- [ ] Шаг 5 / День 5 — полировка, нагрузочный прогон, репетиция демо

## Query API (формат = контракт мока 1:1)

```text
GET /api/v1/bunkers                                  → [{id, name, online, geometry_id}]
GET /api/v1/bunkers/:id/geometry                     → {bunker_id, shape, sensor, beams} (+ETag/304)
GET /api/v1/bunkers/:id/measurements/latest          → последнее измерение + 64 луча
GET /api/v1/bunkers/:id/measurements?from&to&limit&offset → страница БЕЗ beams (limit ≤ 100, как в моке)
GET /api/v1/bunkers/:id/stats?period=day|week|month  → серверные бакеты time_bucket
GET /api/v1/bunkers/:id/buildup                      → зоны налипания (эвристика v1, on-read)
GET /api/v1/health                                   → {edge_pcs: [...]}
```

Защита фронта от лагов: списочные ручки не отдают `beams`, `limit` жёстко ограничен,
графики строятся только из серверных бакетов `stats` (≤ ~1000 точек), включены gzip и CORS.
Тексты ошибок — как у мока: `"Bunker not found"` / `"No measurements"` (latest) / `"No data"` (stats, buildup).

## Подключение EdgePC

Агент отправляет данные на сервер сам (at-least-once); на его стороне задаются:

| Переменная EdgePC | Значение |
| --- | --- |
| `DISPATCH__HTTP__SERVER_URL` | `http://<host>:8000/api/v1` — префикс `/api/v1` обязателен: агент аппендит голые пути `telemetry`/`events`/`health` |
| `DISPATCH__HTTP__AUTH_TOKEN` | то же значение, что `BUNKER_API__EDGE_AUTH_TOKEN`; передаётся заголовком `Authorization: Bearer <token>` |

Семантика ответов (агент парсит только статус-код): `200` — успех, включая
полный дубль; `401` — нет заголовка/схемы, `403` — неверный токен → агент
останавливает диспетчеризацию; `422` — батч отброшен целиком (изоляцию пакетов
делает edge); `429`/5xx — агент ретраит. Тело `POST /health` — снимок агента:
`ts`, `workers`, `pending_count`, `quarantined_count`, `free_bytes`,
`storage_paused`, `cpu_percent`/`memory_percent`/`disk_percent`; `node_id`
агент не шлёт — узел идентифицируется по бункеру (`bunker-1` → `edge-1`).
Каждый из трёх POST продлевает `edge_nodes.last_seen_at`.

## Сидинг демо-истории

```bash
uv run python scripts/seed_demo.py --reset   # 30 дней × 2 бункера через COPY (~20 c)
```

Генератор — прямой порт мока: дрейф уровня, налипание на оси C/F, деградация внешних
лучей. Сид заливает также bunkers/geometries (справочник конфигуратора) и edge_nodes
(узлы сразу online).
