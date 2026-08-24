"""Composition root: единственное место сборки адаптеров и зависимостей."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.application.ingestion.service import IngestionService
from src.config.settings import Settings, get_settings
from src.infrastructure.database.engine import create_engine, create_sessionmaker
from src.infrastructure.database.repositories.event import SqlEventRepository
from src.infrastructure.database.repositories.health import SqlHealthRepository
from src.infrastructure.database.repositories.measurement import (
    SqlMeasurementRepository,
)


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    ingestion: IngestionService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()
    engine = create_engine(settings.database)
    sessions = create_sessionmaker(engine)

    ingestion = IngestionService(
        measurements=SqlMeasurementRepository(sessions),
        events=SqlEventRepository(sessions),
        health=SqlHealthRepository(sessions),
    )
    return Container(
        settings=settings,
        engine=engine,
        sessions=sessions,
        ingestion=ingestion,
    )
