from pydantic import BaseModel, Field

#: An H3 index is 15 hex characters at the resolutions this app uses; 32 is the
#: column width. Bounding both the list and each item turns a malformed or
#: hostile payload into a 422 instead of a database error surfacing as a 500.
MAX_CELLS_PER_PUSH = 5000
MAX_CELL_ID_LENGTH = 32


class CellsPush(BaseModel):
    """Delta of newly-explored cells. Only coarse H3 ids — never coordinates."""

    cells: list[str] = Field(
        default_factory=list,
        max_length=MAX_CELLS_PER_PUSH,
    )


class CellsResponse(BaseModel):
    cells: list[str]
    #: True when more cells remain past `cursor` — pull again to continue.
    has_more: bool = False
    # Null on an empty set: the client stores it verbatim and omits the query
    # param on the next pull.
    #: Opaque — the client stores and replays it, never interprets it.
    cursor: str | None = None
