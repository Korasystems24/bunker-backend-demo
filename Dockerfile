# ── Сборка зависимостей (uv) ────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev


# ── Рантайм ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app . /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# Entrypoint применяет миграции (alembic upgrade head) перед uvicorn.
ENTRYPOINT ["./docker/entrypoint.sh"]