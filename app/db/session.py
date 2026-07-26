from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


def _normalize(url: str) -> str:
    """
    Accept the DSN shapes hosted Postgres providers hand out.

    Neon (and most dashboards) give a `postgresql://` or `postgres://` URL meant
    for psycopg. SQLAlchemy needs the async driver spelled out, and asyncpg
    rejects libpq-only query args like `sslmode` / `channel_binding` — it
    negotiates TLS itself. Normalizing here means the operator can paste the
    connection string verbatim.
    """
    normalized = url
    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql://", 1)
    if normalized.startswith("postgresql://"):
        normalized = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "+asyncpg" in normalized and "?" in normalized:
        base, _, query = normalized.partition("?")
        keep = [
            param
            for param in query.split("&")
            if param and param.split("=")[0] not in {"sslmode", "channel_binding"}
        ]
        normalized = base + ("?" + "&".join(keep) if keep else "")
    return normalized


DATABASE_URL = _normalize(settings.DATABASE_URL)
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# Serverless Postgres (Neon) sits behind a connection pooler that can drop idle
# server-side connections; a client-side pool would then hand out dead sockets.
# NullPool opens per request and lets the provider's pooler do the pooling.
engine = create_async_engine(
    DATABASE_URL,
    future=True,
    poolclass=NullPool if IS_POSTGRES else None,
    connect_args={"ssl": True} if IS_POSTGRES else {},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
