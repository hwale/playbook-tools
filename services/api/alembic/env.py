"""
Alembic environment — tells Alembic how to connect to the database and which
models define the target schema.

Two modes:
  offline — generates SQL without a live DB connection (useful for review)
  online  — connects to the DB and applies migrations directly

Because our app uses an async SQLAlchemy engine (asyncpg), we use
asyncio.run() + run_sync() so Alembic (which is synchronous) can work
with our async setup without needing a second sync driver.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import Base + all models so Alembic can see them in Base.metadata.
# If a model isn't imported here, Alembic won't generate a migration for it.
from app.models import Base  # noqa: F401 — side-effect import
from app.core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the schema Alembic will compare against the live database
# to auto-generate migrations.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Offline mode: emit SQL to stdout without connecting to the DB.
    Useful for reviewing what a migration will do before applying it.
    Run with: alembic upgrade head --sql
    """
    url = get_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Online mode: connect to the live DB and apply migrations.
    We create a temporary async engine just for Alembic, then use
    run_sync() to bridge the async connection into Alembic's sync API.
    """
    url = get_settings().database_url
    engine = create_async_engine(url)

    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
