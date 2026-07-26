import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from app.db.base_class import Base
from app.db.session import DATABASE_URL
from app.models import ExplorationCell  # noqa: F401 — register model metadata

config = context.config

# Reuse the SAME normalized DSN the app runs on (async driver, libpq-only query
# args stripped) — reading the raw setting here would send Alembic down the
# psycopg2 path and fail on a Neon connection string. `%` is doubled because
# configparser treats it as interpolation syntax, and generated passwords
# routinely contain one.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
