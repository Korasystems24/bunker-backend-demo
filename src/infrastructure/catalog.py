"""JSON-адаптер каталога; параметры геометрии загружаются один раз при старте."""

import json
import math
from pathlib import Path

from src.domain.constants import BEAM_COUNT
from src.domain.entities.catalog import BunkerCatalog
from src.domain.entities.geometry import Geometry, GeometryBeam
from src.domain.ports.catalog_provider import CatalogProvider


class JsonCatalogProvider(CatalogProvider):
    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._catalog = BunkerCatalog.model_validate(payload)
        templates = [
            self._catalog.default_geometry,
            *(bunker.geometry for bunker in self._catalog.bunkers if bunker.geometry is not None),
        ]
        for template in templates:
            beam_count = len(template.beam_layout.axes) * len(template.beam_layout.positions)
            if beam_count != BEAM_COUNT:
                raise ValueError(
                    f"geometry template must define {BEAM_COUNT} beams, got {beam_count}"
                )

    @property
    def catalog(self) -> BunkerCatalog:
        return self._catalog

    def geometry_for(self, bunker_id: str) -> Geometry:
        configured = next(
            (bunker for bunker in self._catalog.bunkers if bunker.id == bunker_id),
            None,
        )
        template = (
            configured.geometry
            if configured is not None and configured.geometry is not None
            else self._catalog.default_geometry
        )
        radius_m = template.shape.top_diameter_m / 2
        beams: list[GeometryBeam] = []
        for axis in template.beam_layout.axes:
            azimuth = math.radians(axis.azimuth_deg)
            for position in template.beam_layout.positions:
                distance = radius_m * position.radius_fraction
                beams.append(
                    GeometryBeam(
                        beam_name=f"{axis.name}{position.number}",
                        axis=axis.name,
                        position=position.number,
                        x=round(distance * math.cos(azimuth), 4),
                        y=round(distance * math.sin(azimuth), 4),
                        z=template.beam_layout.z_m,
                    )
                )
        return Geometry(
            bunker_id=bunker_id,
            shape=template.shape,
            sensor=template.sensor,
            beams=tuple(beams),
        )
