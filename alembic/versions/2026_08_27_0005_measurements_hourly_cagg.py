"""Continuous aggregate measurements_hourly: бакеты stats без скана сырых строк.

Блок D плана (день 4): один часовой cagg закрывает day/week/month.
WITH NO DATA обязателен — Alembic гоняет миграции в транзакции, а
create_materialized_view с timescaledb.continuous внутри транзакции
не материализует данные. Историю пишет Ingestion API; cagg обновляется
в real-time. scripts/seed_catalog.py заливает только справочник.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-27

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Каждый элемент — РОВНО ОДИН оператор SQL: asyncpg не выполняет
# несколько операторов за один вызов.
_UP_STATEMENTS: tuple[str, ...] = (
    """
    CREATE MATERIALIZED VIEW measurements_hourly
    WITH (timescaledb.continuous) AS
    SELECT bunker_id,
           time_bucket(INTERVAL '1 hour', ts) AS bucket,
           avg(avg_level) AS avg_level,
           min(min_level) AS min_level,
           max(max_level) AS max_level,
           avg(mass)      AS mass,
           avg(volume)    AS volume,
           min(avg_level) AS min_avg_level,
           max(avg_level) AS max_avg_level,
           count(avg_level) AS sample_count,
           sum(avg_level) AS sum_avg_level
    FROM measurements
    GROUP BY bunker_id, time_bucket(INTERVAL '1 hour', ts)
    WITH NO DATA
    """,
    # Real-time: свежие сырые строки поверх материализованных бакетов,
    # чтобы график «сейчас» не ждал refresh политики.
    """
    ALTER MATERIALIZED VIEW measurements_hourly
        SET (timescaledb.materialized_only = false)
    """,
    """
    CREATE INDEX ix_measurements_hourly_bunker_bucket
        ON measurements_hourly (bunker_id, bucket DESC)
    """,
    """
    SELECT add_continuous_aggregate_policy(
        'measurements_hourly',
        start_offset => INTERVAL '3 days',
        end_offset   => INTERVAL '1 hour',
        schedule_interval => INTERVAL '30 minutes'
    )
    """,
)

_DOWN_STATEMENTS: tuple[str, ...] = (
    "DROP MATERIALIZED VIEW IF EXISTS measurements_hourly CASCADE",
)


def upgrade() -> None:
    for statement in _UP_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWN_STATEMENTS:
        op.execute(statement)
