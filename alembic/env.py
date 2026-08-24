"""Async-окружение Alembic: DSN берётся из настроек приложения (12-factor)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from src.config.settings import get_settings
from src.infrastructure.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные содержат ТОЛЬКО справочные таблицы (bunkers/geometries):
# тайм-серии описываются raw-SQL миграциями (см. versions/0001).
target_metadata = Base.metadata

# '%' в пароле DSN ломает интерполяцию configparser в alembic.ini.
config.set_main_option("sqlalchemy.url", get_settings().database.url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Режим ``--sql``: генерация SQL без подключения к БД."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
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
    """Подключение через asyncpg (NullPool: разовые миграционные сессии)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
