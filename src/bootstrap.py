"""Composition root: единственное место сборки адаптеров и зависимостей."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.application.buildup.detector import RadialSlopeDeviationDetector
from src.application.ingestion.service import IngestionService
from src.application.query.service import QueryService
from src.application.silence.monitor import SilenceMonitor
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
    silence: SilenceMonitor


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()
    engine = create_engine(settings.database)
    sessions = create_sessionmaker(engine)

    health = SqlHealthRepository(sessions)
    bunkers = SqlBunkerRepository(sessions)
    detector = RadialSlopeDeviationDetector(
        outer_position_threshold=settings.buildup.outer_position_threshold,
        deviation_threshold_m=settings.buildup.deviation_threshold_m,
    )
    ingestion = IngestionService(
        measurements=SqlMeasurementRepository(sessions),
        events=SqlEventRepository(sessions),
        health=health,
        bunkers=bunkers,
        buildup=detector,
    )
    query = QueryService(
        measurements=SqlMeasurementRepository(sessions),
        bunkers=bunkers,
        health=health,
        edge_stale_after_sec=settings.api.edge_stale_after_sec,
        buildup=settings.buildup,
    )
    silence = SilenceMonitor(
        health=health,
        stale_after_sec=settings.api.edge_stale_after_sec,
        poll_interval_sec=settings.api.silence_poll_interval_sec,
    )
    return Container(
        settings=settings,
        engine=engine,
        sessions=sessions,
        ingestion=ingestion,
        query=query,
        silence=silence,
    )
