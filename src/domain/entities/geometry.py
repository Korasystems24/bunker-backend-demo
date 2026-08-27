"""Типизированная геометрия бункера и шаблон её размещения."""

from typing import Literal, Self

import pydantic


class GeometryShape(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    type: Literal["truncated_cone"]
    top_diameter_m: float = pydantic.Field(gt=0)
    bottom_diameter_m: float = pydantic.Field(gt=0)
    height_m: float = pydantic.Field(gt=0)


class GeometrySensor(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    x: float
    y: float
    z: float
    tilt_deg: float


class GeometryBeam(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    beam_name: str
    axis: str
    position: int = pydantic.Field(ge=1)
    x: float
    y: float
    z: float


class Geometry(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    bunker_id: str
    shape: GeometryShape
    sensor: GeometrySensor
    beams: tuple[GeometryBeam, ...]


class GeometryAxis(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    name: str = pydantic.Field(min_length=1)
    azimuth_deg: float


class GeometryPosition(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    number: int = pydantic.Field(ge=1)
    radius_fraction: float = pydantic.Field(gt=0, le=1)


class RadialBeamLayout(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    axes: tuple[GeometryAxis, ...]
    positions: tuple[GeometryPosition, ...]
    z_m: float = 0

    @pydantic.model_validator(mode="after")
    def unique_coordinates(self) -> Self:
        axis_names = [axis.name for axis in self.axes]
        positions = [position.number for position in self.positions]
        if not axis_names or len(axis_names) != len(set(axis_names)):
            raise ValueError("beam layout axes must be non-empty and unique")
        if not positions or len(positions) != len(set(positions)):
            raise ValueError("beam layout positions must be non-empty and unique")
        return self


class GeometryTemplate(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    shape: GeometryShape
    sensor: GeometrySensor
    beam_layout: RadialBeamLayout
