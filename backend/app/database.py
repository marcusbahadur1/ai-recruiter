from collections.abc import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.pool import NullPool

from app.config import settings


def _build_db_url():
    """Return a SQLAlchemy URL object with the password from DB_PASSWORD if set.

    Returning a URL object (not str) avoids SQLAlchemy's password redaction
    in __str__ which would pass literal '***' as the password to asyncpg.
    """
    url = make_url(settings.sqlalchemy_database_url)
    if settings.db_password:
        url = url.set(password=settings.db_password)
    return url


_db_url = _build_db_url()

engine = create_async_engine(
    _db_url,
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0, "ssl": "require"},
    poolclass=NullPool,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Celery tasks call asyncio.run() which creates a new event loop per task.
# SQLAlchemy's default pool caches connections with futures bound to the loop
# that opened them; reusing those connections in a new loop raises
# "RuntimeError: Task got Future attached to a different loop".
# NullPool disables connection pooling — each task gets a fresh connection.
#
# Tasks use the Supabase session pooler (port 5432) rather than the transaction
# pooler (port 6543).  In pgbouncer TRANSACTION mode the backend Postgres
# connection is reassigned after every COMMIT, so named prepared statements
# created by one task can persist on the backend connection and collide with
# the same statement names from the next task that lands on that backend —
# causing DuplicatePreparedStatementError.  SESSION mode keeps the same
# backend connection for the entire client session, so prepared statements are
# always unique to the connection and are cleaned up when the connection closes.
def _build_task_db_url():
    url = _build_db_url()
    # Auto-switch from Supabase transaction pooler (port 6543) to session
    # pooler (port 5432).  The host and credentials are identical; only the
    # port changes.  If the URL already uses port 5432 (or a non-Supabase
    # host), it is returned unchanged.
    if url.port == 6543:
        url = url.set(port=5432)
    return url


_task_engine = create_async_engine(
    _build_task_db_url(),
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0, "ssl": "require"},
    poolclass=NullPool,
)

AsyncTaskSessionLocal = async_sessionmaker(
    bind=_task_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async database session."""
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            await session.close()
        except Exception:
            pass
