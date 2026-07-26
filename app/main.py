from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — ensure models are registered before create_all
from app.api.v1.api import api_router
from app.core.config import settings
from app.db.base_class import Base
from app.db.session import IS_POSTGRES, engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Create the schema on boot for the local SQLite database only.

    Deliberately skipped on Postgres: `create_all` and Alembic would then both
    own the schema, and whichever ran first would leave the other's bookkeeping
    inconsistent (a table with no `alembic_version` row). Hosted databases are
    migrated explicitly with `make migrate`.
    """
    if not IS_POSTGRES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Fogline Sync API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
