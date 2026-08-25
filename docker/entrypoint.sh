#!/bin/sh
# Entrypoint api-контейнера: миграции применяются перед стартом приложения.
set -eu

echo "[entrypoint] применяю миграции: alembic upgrade head"
alembic upgrade head

echo "[entrypoint] запускаю uvicorn"
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
