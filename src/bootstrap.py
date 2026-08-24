"""Composition root: единственное место сборки адаптеров и зависимостей."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.config.settings import Settings, get_settings
from src.infrastructure.database.engine import create_engine, create_sessionmaker


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()
    engine = create_engine(settings.database)
    sessions = create_sessionmaker(engine)
    return Container(settings=settings, engine=engine, sessions=sessions)
