from __future__ import annotations

from dataclasses import dataclass

#: Marks a cursor as ours, so a value from an older encoding reads as foreign
#: and is rejected rather than parsed into a plausible wrong position.
_PREFIX = "s:"


@dataclass(frozen=True)
class Cursor:
    """
    Position in an identity's explored set: one commit-ordered sequence number.

    An earlier version carried a timestamp AND a row id, because neither was
    sufficient alone: the id is allocated before commit, so concurrent writers
    can commit out of order and strand a lower id behind a reader's cursor, and
    a shared timestamp cannot separate rows written by a single statement. That
    pair worked, at the cost of recording when each cell was revealed, which is
    exactly the movement history the product promises not to keep.

    `seq` is handed out under a row lock held until commit, so it is total AND
    monotonic in commit order by construction. One column, no clock, and the
    rewind window the old scheme needed disappears with it.

    It stays an opaque string on the wire: the client stores and replays it, and
    the server keeps the freedom to change what is inside.
    """

    seq: int

    def encode(self) -> str:
        return f"{_PREFIX}{self.seq}"

    @classmethod
    def decode(cls, raw: str) -> Cursor | None:
        """Parse a client-supplied cursor. `None` when it is not one of ours."""
        if not raw.startswith(_PREFIX):
            return None
        try:
            seq = int(raw[len(_PREFIX) :])
        except ValueError:
            return None
        return cls(seq=seq) if seq >= 0 else None
