"""add created_at to exploration_cells

The pull cursor moves from the row id to a commit-ordered timestamp: sequence
ids are allocated before commit, so concurrent writers can commit out of order
and a reader between the two commits would skip the lower id permanently.

Revision ID: 0002_cell_created_at
Revises: 0001_init
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_cell_created_at"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exploration_cells",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_exploration_cells_created_at", "exploration_cells", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_exploration_cells_created_at", table_name="exploration_cells")
    op.drop_column("exploration_cells", "created_at")
