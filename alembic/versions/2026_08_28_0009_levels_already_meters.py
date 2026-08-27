"""EdgePC шлёт уровни и высоты лучей в метрах; убрать ошибочное /1000.

Ранее ingest делил avg_level и beam.height на 1000, ожидая миллиметры.
Фактический агент отдаёт метры, поэтому в хранилище оказались ~мм как метры.
Миграция масштабирует уже записанные уровни обратно.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Порог: ошибочно сконвертированные значения — доли метра (типично ~0.002).
# Реальные метры после фикса (>1) не трогаем, если миграция догоняет живой поток.
_SCALE_THRESHOLD = 1.0

_UP_SCALE: tuple[str, ...] = (
    f"""
    UPDATE measurements
       SET avg_level = avg_level * 1000,
           min_level = min_level * 1000,
           max_level = max_level * 1000
     WHERE COALESCE(avg_level, min_level, max_level, 0) > 0
       AND COALESCE(avg_level, min_level, max_level) < {_SCALE_THRESHOLD}
    """,
    f"""
    UPDATE beam_readings
       SET height = height * 1000
     WHERE height IS NOT NULL
       AND height > 0
       AND height < {_SCALE_THRESHOLD}
    """,
    f"""
    UPDATE buildup_zones
       SET deviation_m = deviation_m * 1000
     WHERE deviation_m > 0
       AND deviation_m < {_SCALE_THRESHOLD}
    """,
)

_DOWN_SCALE: tuple[str, ...] = (
    f"""
    UPDATE measurements
       SET avg_level = avg_level / 1000,
           min_level = min_level / 1000,
           max_level = max_level / 1000
     WHERE COALESCE(avg_level, min_level, max_level, 0) >= {_SCALE_THRESHOLD}
    """,
    f"""
    UPDATE beam_readings
       SET height = height / 1000
     WHERE height IS NOT NULL
       AND height >= {_SCALE_THRESHOLD}
    """,
    f"""
    UPDATE buildup_zones
       SET deviation_m = deviation_m / 1000
     WHERE deviation_m >= {_SCALE_THRESHOLD}
    """,
)

_REFRESH = "CALL refresh_continuous_aggregate('measurements_hourly', NULL, NULL)"


def upgrade() -> None:
    for statement in _UP_SCALE:
        op.execute(statement)
    with op.get_context().autocommit_block():
        op.execute(_REFRESH)


def downgrade() -> None:
    for statement in _DOWN_SCALE:
        op.execute(statement)
    with op.get_context().autocommit_block():
        op.execute(_REFRESH)
