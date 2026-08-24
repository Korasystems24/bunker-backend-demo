#!/bin/sh
# Entrypoint api-контейнера: миграции применяются перед стартом приложения.
set -eu

echo "[entrypoint] применяю миграции: alembic upgrade head"
alembic upgrade head

echo "[entrypoint] запускаю uvicorn"
exec uvicorn src.main:app \
    --host "${BUNKER_API__HOST:-0.0.0.0}" \
    --port "${BUNKER_API__PORT:-8000}"