from dotenv import load_dotenv
load_dotenv()
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Pull in all models so their metadata is registered ────────────────────────
from app.database import Base
import app.models  # noqa: F401 — side-effect import; registers all mappers

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from environment (never rely on alembic.ini value).
# Uses SQLALCHEMY_DATABASE_URL + optional DB_PASSWORD (same pattern as database.py).
# DB_PASSWORD is stored separately to avoid URL-encoding issues with special chars.
from sqlalchemy.engine import make_url as _make_url

_raw_url = os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not _raw_url:
    raise RuntimeError(
        "Set SQLALCHEMY_DATABASE_URL (or DATABASE_URL) in your .env before running migrations."
    )
_db_password = os.environ.get("DB_PASSWORD")
_url_obj = _make_url(_raw_url)
if _db_password:
    _url_obj = _url_obj.set(password=_db_password)

# Async URL used by async_engine_from_config at runtime
database_url = _url_obj

# Alembic config needs a plain string with a sync driver scheme
config.set_main_option(
    "sqlalchemy.url",
    str(_url_obj).replace("postgresql+asyncpg://", "postgresql://"),
)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    async_config = config.get_section(config.config_ini_section, {})
    async_config["sqlalchemy.url"] = database_url

    connectable = async_engine_from_config(
        async_config,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
