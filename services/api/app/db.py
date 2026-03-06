from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


@lru_cache
def _get_engine():
    """
    Create the async SQLAlchemy engine once and cache it.

    The engine manages a connection pool — a set of reusable database
    connections. Creating a new engine per request would open and close
    a new connection every time, paying TCP + TLS setup cost repeatedly.
    One cached engine means connections are opened once and reused.

    pool_pre_ping=True: before handing a connection from the pool to your
    code, SQLAlchemy sends a cheap "SELECT 1" to check it's still alive.
    Without this, stale connections (e.g., after Postgres restarts) silently
    fail mid-request.
    """
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Session factory — a callable that produces new AsyncSession objects.
    expire_on_commit=False means ORM objects stay usable after a commit,
    which matters in async code where you might access attributes after
    the session has been committed.
    """
    return async_sessionmaker(_get_engine(), expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Yields one database session per request, then
    closes it when the request finishes — success or exception.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Document))
    """
    async with _get_session_factory()() as session:
        yield session
