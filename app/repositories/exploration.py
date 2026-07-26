from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import IS_POSTGRES
from app.models.exploration_cell import ExplorationCell, ExplorationSequence

# Pure data access. No dedup, no cursor semantics, no commit — those are the
# service's job, so callers stay free to compose several writes in one
# transaction.


async def _reserve_sequence(db: AsyncSession, user_id: str, count: int) -> int:
    """
    Reserve `count` consecutive positions for this identity, returning the first.

    The counter row is taken FOR UPDATE and the lock is held until the caller
    commits, which is what makes the numbers land in commit order rather than in
    the order the transactions started. On SQLite the clause is not emitted and
    is not needed: the engine serialises writers at the database level.

    The row is created on first use with ON CONFLICT DO NOTHING rather than
    read-then-insert, because two devices syncing for the first time in the same
    moment would otherwise both see nothing and both insert.
    """
    insert = pg_insert if IS_POSTGRES else sqlite_insert
    await db.execute(
        insert(ExplorationSequence)
        .values(user_id=user_id, next_seq=1)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )

    stmt = select(ExplorationSequence).where(ExplorationSequence.user_id == user_id)
    if IS_POSTGRES:
        stmt = stmt.with_for_update()

    counter = (await db.execute(stmt)).scalar_one()
    start = counter.next_seq
    counter.next_seq = start + count
    await db.flush()
    return int(start)


async def insert_cells_ignoring_duplicates(
    db: AsyncSession, user_id: str, cells: list[str]
) -> None:
    """
    Insert cells, skipping any that already exist for this identity.

    Uses the dialect's native ON CONFLICT DO NOTHING rather than read-then-diff:
    the read-then-diff version races two concurrent syncs for the same identity
    (the app's foreground watcher and its background task can both flush), and
    both would then insert the same cell and hit the unique constraint. Letting
    the database arbitrate makes the write idempotent under concurrency.
    """
    if not cells:
        return

    start = await _reserve_sequence(db, user_id, len(cells))
    today = datetime.now(timezone.utc).date()
    rows = [
        {
            "user_id": user_id,
            "cell_id": cell,
            "seq": start + offset,
            "revealed_on": today,
        }
        for offset, cell in enumerate(cells)
    ]

    insert = pg_insert if IS_POSTGRES else sqlite_insert
    stmt = (
        insert(ExplorationCell)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["user_id", "cell_id"])
    )
    await db.execute(stmt)


async def select_cells_after(
    db: AsyncSession,
    user_id: str,
    after_seq: int | None,
    limit: int,
) -> list[tuple[int, str]]:
    """
    Rows (seq, cell_id) for this identity strictly after `after_seq`, in commit
    order, oldest first.

    One column is enough for a total order here, unlike an autoincrement id:
    `seq` is handed out under a lock held to commit, so a row can never surface
    behind a position a reader has already passed.

    Bounded: a client whose cursor was wiped (reinstall, cleared storage) asks
    for the whole history, and an unbounded response would be a multi-megabyte
    payload the device then has to insert in one go.
    """
    stmt = select(ExplorationCell.seq, ExplorationCell.cell_id).where(
        ExplorationCell.user_id == user_id
    )
    if after_seq is not None:
        stmt = stmt.where(ExplorationCell.seq > after_seq)

    stmt = stmt.order_by(ExplorationCell.seq).limit(limit)
    return [(int(row.seq), row.cell_id) for row in (await db.execute(stmt)).all()]
