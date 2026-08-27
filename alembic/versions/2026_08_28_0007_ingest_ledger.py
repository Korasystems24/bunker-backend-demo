"""Stable telemetry deduplication independent of packet timestamps.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ingest_ledger (
            bunker_id  TEXT NOT NULL REFERENCES bunkers(id) ON DELETE CASCADE,
            event_id   UUID NOT NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (bunker_id, event_id)
        )
        """
    )
    op.execute(
        """
        INSERT INTO ingest_ledger (bunker_id, event_id, received_at)
        SELECT bunker_id, event_id, min(ts)
        FROM measurements
        GROUP BY bunker_id, event_id
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE ingest_ledger")
