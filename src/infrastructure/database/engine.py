"""Асинхронный движок SQLAlchemy (asyncpg) и фабрика сессий."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(
        settings.url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        echo=settings.echo,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # Одна транзакция = один write-запрос (unit of work на шаге 2).
    return async_sessionmaker(engine, expire_on_commit=False)
