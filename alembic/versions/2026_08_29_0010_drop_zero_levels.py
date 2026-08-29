"""Нулевой уровень — сбой радара, не пустой бункер.

avg_level=0 обнуляем (NULL). min/max пересчитываем по лучам с height>0
без жёстко ненадёжных флагов, затем обновляем hourly cagg.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HARD_FLAGS = r"(^|, )(Disabled|DistanceNotUpdating|NotUsed|Unknown)(,|$)"

_NULL_ZERO_AVG = """
    UPDATE measurements
       SET avg_level = NULL
     WHERE avg_level IS NOT NULL
       AND avg_level <= 0
"""

_RECOMPUTE_MIN_MAX = f"""
    UPDATE measurements AS m
       SET min_level = s.min_h,
           max_level = s.max_h
      FROM (
        SELECT bunker_id,
               ts,
               min(height) FILTER (
                 WHERE height > 0
                   AND beam_flags !~ '{_HARD_FLAGS}'
               ) AS min_h,
               max(height) FILTER (
                 WHERE height > 0
                   AND beam_flags !~ '{_HARD_FLAGS}'
               ) AS max_h
          FROM beam_readings
         GROUP BY bunker_id, ts
      ) AS s
     WHERE m.bunker_id = s.bunker_id
       AND m.ts = s.ts
"""

_REFRESH = "CALL refresh_continuous_aggregate('measurements_hourly', NULL, NULL)"


def upgrade() -> None:
    op.execute(_NULL_ZERO_AVG)
    op.execute(_RECOMPUTE_MIN_MAX)
    with op.get_context().autocommit_block():
        op.execute(_REFRESH)


def downgrade() -> None:
    # Обратный пересчёт нулей невосстановим: исходные 0 уже стёрты.
    pass
