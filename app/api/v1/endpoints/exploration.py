from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_identity
from app.db.session import get_db
from app.schemas.exploration import CellsPush, CellsResponse
from app.services import exploration_service

router = APIRouter()


@router.post("/cells", status_code=status.HTTP_204_NO_CONTENT)
async def push_cells(
    payload: CellsPush,
    identity: str = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Union newly-explored cells into this identity's grow-only set."""
    await exploration_service.record_explored_cells(db, identity, payload.cells)


@router.get("/cells", response_model=CellsResponse)
async def pull_cells(
    # Bounded so a hostile value cannot reach the decoder; the cursor itself is
    # opaque, so its FORMAT is validated in the service rather than here.
    since: str | None = Query(default=None, max_length=64),
    identity: str = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> CellsResponse:
    """Cells added since `since` (cross-device merge) plus the next cursor."""
    page = await exploration_service.read_explored_cells(db, identity, since)
    return CellsResponse(cells=page.cells, cursor=page.cursor, has_more=page.has_more)
