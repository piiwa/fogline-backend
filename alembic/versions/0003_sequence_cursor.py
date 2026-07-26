"""replace the timestamp cursor with a per-identity commit sequence

The pull cursor was (created_at, id). It worked, but storing when each cell was
revealed lets anyone with database access sort an identity's hexagons into the
path that person walked, pauses included — the raw trace the product promises
not to keep, rebuilt one column at a time.

`seq` is reserved under a row lock held until commit, so it is total and
monotonic in commit order without being a clock. `revealed_on` keeps day
granularity, which is what retention needs and no more.

Revision ID: 0003_sequence_cursor
Revises: 0002_cell_created_at
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_sequence_cursor"
down_revision = "0002_cell_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exploration_sequences",
        sa.Column("user_id", sa.String(length=128), primary_key=True),
        sa.Column("next_seq", sa.BigInteger(), nullable=False, server_default="1"),
    )

    op.add_column("exploration_cells", sa.Column("seq", sa.BigInteger(), nullable=True))
    op.add_column("exploration_cells", sa.Column("revealed_on", sa.Date(), nullable=True))

    # Existing rows are backfilled from the order they already had, which is the
    # best available approximation and preserves every client's position.
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            UPDATE exploration_cells AS c
            SET seq = ranked.rn, revealed_on = c.created_at::date
            FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id ORDER BY created_at, id
                ) AS rn
                FROM exploration_cells
            ) AS ranked
            WHERE ranked.id = c.id
            """
        )
        op.execute(
            """
            INSERT INTO exploration_sequences (user_id, next_seq)
            SELECT user_id, MAX(seq) + 1 FROM exploration_cells GROUP BY user_id
            """
        )
    else:
        op.execute(
            """
            UPDATE exploration_cells
            SET seq = (
                SELECT COUNT(*) FROM exploration_cells AS o
                WHERE o.user_id = exploration_cells.user_id
                  AND (o.created_at < exploration_cells.created_at
                       OR (o.created_at = exploration_cells.created_at
                           AND o.id <= exploration_cells.id))
            ),
            revealed_on = date(created_at)
            """
        )
        op.execute(
            """
            INSERT INTO exploration_sequences (user_id, next_seq)
            SELECT user_id, MAX(seq) + 1 FROM exploration_cells GROUP BY user_id
            """
        )

    with op.batch_alter_table("exploration_cells") as batch:
        batch.alter_column("seq", nullable=False)
        batch.alter_column("revealed_on", nullable=False)

    op.create_index("ix_exploration_cells_user_seq", "exploration_cells", ["user_id", "seq"])
    op.create_index(
        "ix_exploration_cells_revealed_on", "exploration_cells", ["revealed_on"]
    )
    op.drop_index("ix_exploration_cells_created_at", table_name="exploration_cells")
    op.drop_column("exploration_cells", "created_at")


def downgrade() -> None:
    op.add_column(
        "exploration_cells",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_exploration_cells_created_at", "exploration_cells", ["created_at"])
    op.drop_index("ix_exploration_cells_revealed_on", table_name="exploration_cells")
    op.drop_index("ix_exploration_cells_user_seq", table_name="exploration_cells")
    op.drop_column("exploration_cells", "revealed_on")
    op.drop_column("exploration_cells", "seq")
    op.drop_table("exploration_sequences")
