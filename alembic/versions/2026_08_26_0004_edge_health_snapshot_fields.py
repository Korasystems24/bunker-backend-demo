"""Поля снимка health EdgePC в edge_nodes: workers/очереди/хост-метрики.

POST /health несёт байтовый контракт EdgePC (ts, workers, pending_count,
quarantined_count, free_bytes, storage_paused, *_percent). Храним последний
снапшот целиком для диагностики; cpu/ram/disk остаются колонками из схемы v1
(в них пишутся cpu_percent/memory_percent/disk_percent), ts агента — в edge_time.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE edge_nodes ADD COLUMN workers JSONB")
    op.execute("ALTER TABLE edge_nodes ADD COLUMN pending_count INTEGER")
    op.execute("ALTER TABLE edge_nodes ADD COLUMN quarantined_count INTEGER")
    op.execute("ALTER TABLE edge_nodes ADD COLUMN free_bytes BIGINT")
    op.execute("ALTER TABLE edge_nodes ADD COLUMN storage_paused BOOLEAN")


def downgrade() -> None:
    op.execute("ALTER TABLE edge_nodes DROP COLUMN storage_paused")
    op.execute("ALTER TABLE edge_nodes DROP COLUMN free_bytes")
    op.execute("ALTER TABLE edge_nodes DROP COLUMN quarantined_count")
    op.execute("ALTER TABLE edge_nodes DROP COLUMN pending_count")
    op.execute("ALTER TABLE edge_nodes DROP COLUMN workers")
