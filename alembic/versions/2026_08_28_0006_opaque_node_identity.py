"""Treat bunker_id as an opaque edge-node identity.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE alerts AS a
            SET node_id = n.bunker_id
            FROM edge_nodes AS n
            WHERE a.node_id = n.node_id
              AND n.bunker_id IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE edge_nodes
            SET node_id = bunker_id
            WHERE bunker_id IS NOT NULL
              AND node_id IS DISTINCT FROM bunker_id
            """
        )
    )
    op.create_check_constraint(
        "ck_bunkers_id_length",
        "bunkers",
        "char_length(id) BETWEEN 1 AND 128",
    )
    op.create_check_constraint(
        "ck_edge_nodes_node_id_length",
        "edge_nodes",
        "char_length(node_id) BETWEEN 1 AND 128",
    )


def downgrade() -> None:
    op.drop_constraint("ck_edge_nodes_node_id_length", "edge_nodes", type_="check")
    op.drop_constraint("ck_bunkers_id_length", "bunkers", type_="check")
    # Старое вычисление node_id было неоднозначным, поэтому значения данных
    # намеренно не преобразуются обратно при downgrade.
