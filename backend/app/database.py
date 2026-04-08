from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.pool import NullPool

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    connect_args={"statement_cache_size": 0},
    echo=True,
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
_task_engine = create_async_engine(
    settings.database_url,
    connect_args={"statement_cache_size": 0},
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
    async with AsyncSessionLocal() as session:
        yield session
