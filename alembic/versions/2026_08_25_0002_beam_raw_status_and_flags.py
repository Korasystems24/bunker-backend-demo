"""beam_readings под реальный контракт edge: raw_status nullable + флаги строкой.

Beam из пакета несёт raw_status (int | None) и кортеж строковых статусов
WCF (см. domain.value_objects.beam_status). Храним оба представления:
raw_status — для аналитики, beam_flags ('Fault, NotUsed', ...) — как
отдаёт фронт-контракт мока.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE beam_readings RENAME COLUMN status TO raw_status")
    op.execute("ALTER TABLE beam_readings ALTER COLUMN raw_status DROP NOT NULL")
    op.execute("ALTER TABLE beam_readings ADD COLUMN beam_flags TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE beam_readings DROP COLUMN beam_flags")
    op.execute("ALTER TABLE beam_readings ALTER COLUMN raw_status SET NOT NULL")
    op.execute("ALTER TABLE beam_readings RENAME COLUMN raw_status TO status")
