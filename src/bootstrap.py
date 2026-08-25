"""Composition root: единственное место сборки адаптеров и зависимостей."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.application.ingestion.service import IngestionService
from src.application.query.service import QueryService
from src.config.settings import Settings, get_settings
from src.infrastructure.database.engine import create_engine, create_sessionmaker
from src.infrastructure.database.repositories.bunker import SqlBunkerRepository
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
    query: QueryService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()
    engine = create_engine(settings.database)
    sessions = create_sessionmaker(engine)

    ingestion = IngestionService(
        measurements=SqlMeasurementRepository(sessions),
        events=SqlEventRepository(sessions),
        health=SqlHealthRepository(sessions),
    )
    query = QueryService(
        measurements=SqlMeasurementRepository(sessions),
        bunkers=SqlBunkerRepository(sessions),
        health=SqlHealthRepository(sessions),
        edge_stale_after_sec=settings.api.edge_stale_after_sec,
        buildup=settings.buildup,
    )
    return Container(
        settings=settings,
        engine=engine,
        sessions=sessions,
        ingestion=ingestion,
        query=query,
    )
