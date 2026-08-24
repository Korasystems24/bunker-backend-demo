"""ORM-модели проекта (SQLAlchemy 2.x, DeclarativeBase).

ORM используется ТОЛЬКО для справочных таблиц (bunkers, geometries);
вся телеметрия идёт через raw-SQL Gateway (план, блок C).
"""

from src.infrastructure.database.models.base import Base
from src.infrastructure.database.models.reference import BunkerModel, GeometryModel

__all__ = ["Base", "BunkerModel", "GeometryModel"]
