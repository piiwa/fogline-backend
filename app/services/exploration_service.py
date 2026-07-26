from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import exploration as repo
from app.services.exploration_cursor import Cursor

# Business rules for the exploration set live here — the endpoint stays
# transport-only and the repository stays data-only.


#: Cells returned per pull. Bounds both the response size and the batch the
#: client has to insert; the cursor makes the remainder resumable.
PAGE_SIZE = 2000


@dataclass(frozen=True)
class CellPage:
    """A slice of an identity's explored set, plus the cursor to resume from."""

    cells: list[str]
    #: Opaque to the client — it stores and replays it, nothing more.
    cursor: str | None
    #: True when more cells remain past `cursor` — the client should pull again.
    has_more: bool


async def record_explored_cells(db: AsyncSession, user_id: str, cells: list[str]) -> None:
    """
    Add cells to an identity's grow-only set.

    Deduplicates within the batch before touching the database: a client can
    legitimately send the same cell twice in one payload (two fixes inside one
    hexagon), and some dialects reject a multi-row INSERT that conflicts with
    itself even under ON CONFLICT DO NOTHING.
    """
    unique = list(dict.fromkeys(cells))
    if not unique:
        return
    await repo.insert_cells_ignoring_duplicates(db, user_id, unique)
    await db.commit()


async def read_explored_cells(db: AsyncSession, user_id: str, since: str | None) -> CellPage:
    """
    Cells added after `since`, with the cursor to resume from.

    An unparseable cursor is treated as "from the beginning" rather than an
    error: cursors are opaque and may outlive an encoding change, and re-sending
    a set the client already has costs nothing — it merges by union. The
    transport layer still rejects a cursor of the wrong TYPE, so a genuine
    client bug is not hidden.
    """
    after = Cursor.decode(since) if since is not None else None

    rows = await repo.select_cells_after(db, user_id, after.seq if after else None, limit=PAGE_SIZE)
    if not rows:
        return CellPage(cells=[], cursor=since, has_more=False)

    # No rewind window. Positions are reserved under a lock held to commit, so a
    # row cannot appear behind a cursor the reader has already passed — the
    # failure the old timestamp cursor had to compensate for cannot occur.
    last_seq = rows[-1][0]
    return CellPage(
        cells=[cell for _, cell in rows],
        cursor=Cursor(seq=last_seq).encode(),
        has_more=len(rows) == PAGE_SIZE,
    )
