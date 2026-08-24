# backend-demo — серверная часть системы мониторинга бункеров

Приём телеметрии от EdgePC-агента, хранение временных рядов в PostgreSQL +
TimescaleDB и Query API для фронтенда. Реализация плана `docs/backend-demo-plan.md`.

## Стек

Python 3.12 · FastAPI · SQLAlchemy 2.x (async) · asyncpg · Alembic ·
pydantic-settings · loguru · TimescaleDB (pg16) · Docker Compose · ruff + basedpyright.

## Структура

```text
src/
├── main.py                  # app factory + lifespan
├── bootstrap.py             # composition root (сборка зависимостей)
├── config/settings.py       # pydantic-settings, секции BUNKER_*
├── logging_config.py        # loguru (+ request_id extra)
├── api/
│   ├── ops.py               # GET /healthz (liveness самого API)
│   └── schemas/             # DTO
├── domain/                  # порты и сущности (контракт edge — шаг 2)
└── infrastructure/database/
    ├── engine.py            # async engine + sessionmaker (asyncpg)
    └── models/              # ORM ТОЛЬКО справочных таблиц (bunkers, geometries)
alembic/versions/            # схема v1: гипертаблицы, политики Timescale
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
- [ ] Шаг 2 / День 2 — Ingestion API (`/telemetry`, `/events`, `/health`), дедуп, X-API-Key, контрактные тесты
- [ ] Шаг 3 / День 3 — Query API для фронта, seed_demo, CORS/gzip
- [ ] Шаг 4 / День 4 — buildup v1, SilenceMonitor, continuous aggregates
- [ ] Шаг 5 / День 5 — полировка, нагрузочный прогон, репетиция демо
