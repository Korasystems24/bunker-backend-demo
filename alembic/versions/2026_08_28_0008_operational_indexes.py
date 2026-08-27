"""Indexes not already covered by time-series primary keys.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # measurements, beam_readings and buildup_zones already have primary-key
    # indexes beginning with (bunker_id, ts); duplicating them would slow ingest.
    op.create_index("ix_edge_nodes_bunker_id", "edge_nodes", ["bunker_id"])
    op.create_index(
        "ix_alerts_open_silence",
        "alerts",
        ["node_id"],
        postgresql_where=sa.text("type = 'silence_started' AND resolved_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_open_silence", table_name="alerts")
    op.drop_index("ix_edge_nodes_bunker_id", table_name="edge_nodes")
