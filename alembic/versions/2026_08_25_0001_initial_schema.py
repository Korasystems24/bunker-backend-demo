"""Каркас схемы v1: справочные таблицы + тайм-серии Timescale + политики.

Реализует раздел 4 плана (backend-demo-plan.md):

- справочные таблицы: bunkers, geometries, edge_nodes, alerts;
- события edge с дедупом по PK: edge_events;
- гипертаблицы: measurements и beam_readings (chunk = 1 день);
- индекс дедупликации at-least-once: ux_measurements_packet;
- политики Timescale: компрессия чанков старше 7 дней,
  ретенция сырых лучей 180 дней.

Revision ID: 0001
Revises:
Create Date: 2026-08-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Каждый элемент — РОВНО ОДИН оператор SQL: asyncpg не выполняет
# несколько операторов за один вызов.
_UP_STATEMENTS: tuple[str, ...] = (
    """
    CREATE EXTENSION IF NOT EXISTS timescaledb
    """,
    # ── Справочные таблицы (обычный ORM-мир) ──────────────────────────────
    """
    CREATE TABLE bunkers (
        id         TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE geometries (
        bunker_id  TEXT PRIMARY KEY REFERENCES bunkers(id),
        shape      JSONB NOT NULL,
        sensor     JSONB NOT NULL,
        beams      JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # События edge — низкий объём; дедуп at-least-once по PK.
    """
    CREATE TABLE edge_events (
        bunker_id   TEXT NOT NULL,
        event_id    UUID NOT NULL,
        ts          TIMESTAMPTZ NOT NULL,
        type        TEXT NOT NULL,
        payload     JSONB NOT NULL,
        received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (bunker_id, event_id)
    )
    """,
    # Состояние edge-узлов (обновляется POST /health и касанием телеметрии).
    """
    CREATE TABLE edge_nodes (
        node_id      TEXT PRIMARY KEY,
        bunker_id    TEXT REFERENCES bunkers(id),
        last_seen_at TIMESTAMPTZ,
        cpu          REAL,
        ram          REAL,
        disk         REAL,
        edge_time    TIMESTAMPTZ,
        status       TEXT NOT NULL DEFAULT 'unknown'
    )
    """,
    """
    CREATE TABLE alerts (
        id           BIGSERIAL PRIMARY KEY,
        node_id      TEXT NOT NULL,
        type         TEXT NOT NULL,
        raised_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        resolved_at  TIMESTAMPTZ,
        last_seen_at TIMESTAMPTZ
    )
    """,
    # ── Тайм-серии (мир Timescale) ────────────────────────────────────────
    # PK гипертаблицы обязан включать колонку времени.
    """
    CREATE TABLE measurements (
        bunker_id TEXT NOT NULL,
        event_id  UUID NOT NULL,
        ts        TIMESTAMPTZ NOT NULL,
        avg_level REAL,
        min_level REAL,
        max_level REAL,
        volume    REAL,
        mass      REAL,
        PRIMARY KEY (bunker_id, ts, event_id)
    )
    """,
    """
    CREATE TABLE beam_readings (
        bunker_id TEXT NOT NULL,
        ts        TIMESTAMPTZ NOT NULL,
        beam_name TEXT NOT NULL,
        height    REAL,
        status    SMALLINT NOT NULL DEFAULT 0,
        PRIMARY KEY (bunker_id, ts, beam_name)
    )
    """,
    # Обычная таблица (по плану гипертаблизируются только measurements/beam_readings);
    # читается «последняя запись на бункер», пишется при ингесте.
    """
    CREATE TABLE buildup_zones (
        bunker_id          TEXT NOT NULL,
        ts                 TIMESTAMPTZ NOT NULL,
        axis               TEXT NOT NULL,
        severity           TEXT NOT NULL,
        score              REAL NOT NULL,
        deviation_m        REAL NOT NULL,
        affected_positions INT[] NOT NULL DEFAULT '{}',
        algorithm_version  TEXT NOT NULL,
        PRIMARY KEY (bunker_id, ts, axis)
    )
    """,
    """
    SELECT create_hypertable('measurements', 'ts',
                             chunk_time_interval => INTERVAL '1 day')
    """,
    """
    SELECT create_hypertable('beam_readings', 'ts',
                             chunk_time_interval => INTERVAL '1 day')
    """,
    # Дедуп at-least-once: повторная доставка несёт ТОТ ЖЕ ts (гарантия outbox),
    # поэтому UNIQUE (bunker_id, event_id, ts) достаточен и допустим на
    # гипертаблице (уник включает колонку времени).
    """
    CREATE UNIQUE INDEX ux_measurements_packet
        ON measurements (bunker_id, event_id, ts)
    """,
    # Компрессия: чанки старше 7 дней сжимаются (~90% экономии).
    """
    ALTER TABLE measurements SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'bunker_id',
        timescaledb.compress_orderby = 'ts DESC'
    )
    """,
    """
    ALTER TABLE beam_readings SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'bunker_id, beam_name',
        timescaledb.compress_orderby = 'ts DESC'
    )
    """,
    "SELECT add_compression_policy('measurements', INTERVAL '7 days')",
    "SELECT add_compression_policy('beam_readings', INTERVAL '7 days')",
    # Ретенция: сырые лучи старше 180 дней удаляются (агрегаты остаются).
    "SELECT add_retention_policy('beam_readings', INTERVAL '180 days')",
)

_DOWN_STATEMENTS: tuple[str, ...] = (
    "DROP TABLE IF EXISTS buildup_zones CASCADE",
    "DROP TABLE IF EXISTS beam_readings CASCADE",
    "DROP TABLE IF EXISTS measurements CASCADE",
    "DROP TABLE IF EXISTS alerts CASCADE",
    "DROP TABLE IF EXISTS edge_nodes CASCADE",
    "DROP TABLE IF EXISTS edge_events CASCADE",
    "DROP TABLE IF EXISTS geometries CASCADE",
    "DROP TABLE IF EXISTS bunkers CASCADE",
)


def upgrade() -> None:
    for statement in _UP_STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    for statement in _DOWN_STATEMENTS:
        op.execute(sa.text(statement))
