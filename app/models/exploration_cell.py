from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ExplorationSequence(Base):
    """
    Per-identity monotonic counter, handed out under a row lock.

    It exists so the pull cursor can be ordered by something assigned in COMMIT
    order without being a clock. A plain autoincrement id cannot do it: values
    are allocated before commit, so two concurrent writers can commit in the
    opposite order and leave a lower id permanently behind a reader's cursor. A
    timestamp can do it, but a timestamp per cell IS the movement history the
    product promises not to keep.

    Taking this row FOR UPDATE holds the lock until commit, so numbers land in
    the same order the transactions do. Contention is between one person's own
    devices, which is to say almost none.
    """

    __tablename__ = "exploration_sequences"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    next_seq: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


class ExplorationCell(Base):
    """
    One explored H3 cell for one identity. The (user_id, cell_id) uniqueness is
    what makes the set grow-only and pushes idempotent — the store is a G-Set.
    Cells are pulled in commit order via `seq`.
    """

    __tablename__ = "exploration_cells"
    __table_args__ = (
        UniqueConstraint("user_id", "cell_id", name="uq_user_cell"),
        Index("ix_exploration_cells_user_seq", "user_id", "seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    cell_id: Mapped[str] = mapped_column(String(32), index=True)

    #: Position in this identity's commit-ordered stream. The whole pull cursor.
    #:
    #: Gaps are expected and harmless: numbers are reserved before the insert, so
    #: a cell that is already present consumes one and inserts nothing.
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: The DAY the cell was revealed, deliberately no finer.
    #:
    #: A per-cell timestamp lets anyone with database access sort an identity's
    #: hexagons into the exact path that person walked, pauses included. That is
    #: the raw trace the brief forbids sending to a server, rebuilt one column at
    #: a time. Day granularity keeps what retention needs (how old is this row)
    #: and drops what it does not (in which order, how fast).
    revealed_on: Mapped[date] = mapped_column(
        Date,
        default=lambda: datetime.now(timezone.utc).date(),
        nullable=False,
        index=True,
    )
