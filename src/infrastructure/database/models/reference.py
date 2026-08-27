"""Справочные таблицы: бункеры и их геометрия (мир ORM)."""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class BunkerModel(Base):
    """Бункер. id — строка ('bunker-1')."""

    __tablename__ = "bunkers"

    id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class GeometryModel(Base):
    """Геометрия бункера: форма, датчик и лучи (JSONB)."""

    __tablename__ = "geometries"

    bunker_id: Mapped[str] = mapped_column(
        sa.Text,
        sa.ForeignKey("bunkers.id"),
        primary_key=True,
    )
    shape: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sensor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    beams: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
