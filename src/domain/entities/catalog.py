"""Версионируемый каталог имён бункеров и шаблона геометрии."""

import pydantic

from src.domain.entities.geometry import GeometryTemplate


class CatalogBunker(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    id: str = pydantic.Field(min_length=1, max_length=128)
    name: str = pydantic.Field(min_length=1, max_length=256)
    geometry: GeometryTemplate | None = None


class BunkerCatalog(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    version: int = pydantic.Field(ge=1)
    default_geometry: GeometryTemplate
    bunkers: tuple[CatalogBunker, ...]

    @pydantic.model_validator(mode="after")
    def unique_bunker_ids(self) -> "BunkerCatalog":
        ids = [bunker.id for bunker in self.bunkers]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog contains duplicate bunker ids")
        return self
