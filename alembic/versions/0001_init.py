"""init exploration_cells

Revision ID: 0001_init
Revises:
Create Date: 2026-07-24
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exploration_cells",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("cell_id", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "cell_id", name="uq_user_cell"),
    )
    op.create_index("ix_exploration_cells_user_id", "exploration_cells", ["user_id"])
    op.create_index("ix_exploration_cells_cell_id", "exploration_cells", ["cell_id"])


def downgrade() -> None:
    op.drop_index("ix_exploration_cells_cell_id", table_name="exploration_cells")
    op.drop_index("ix_exploration_cells_user_id", table_name="exploration_cells")
    op.drop_table("exploration_cells")
