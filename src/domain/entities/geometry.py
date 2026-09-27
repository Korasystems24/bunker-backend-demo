"""Типизированная геометрия бункера и шаблон её размещения."""

from typing import Literal, Self

import pydantic


class GeometryShape(pydantic.BaseModel):
    """Производственная модель сосуда ("tiered_rect", из Конфигуратора):
    прямоугольный в плане бункер, у которого видимая 3D-оболочка — две части
    снизу вверх: (1) простой прямоугольник постоянной ширины
    bottom_x_m x bottom_y_m от bottom_height_m до middle_height_m, и (2) одна
    прямая трапеция выше него до vessel_height_m (верх/крыша сосуда),
    расширяющаяся до top_x_m x top_y_m. middle_x_m/middle_y_m/top_height_m в
    саму стенку не участвуют (нужны для расчёта объёма/страппинг-таблицы, не
    для 3D-оболочки — см. src/features/3d/BunkerShape.tsx во фронтенде).
    `rotation_deg` — поворот сечения вокруг вертикальной оси (OZ), всегда
    кратен 90°. `full_volume_m3` — справочная ёмкость сосуда, backend её не
    использует для расчёта объёма руды (это `measurement.volume`)."""

    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    type: Literal["tiered_rect"]
    bottom_x_m: float = pydantic.Field(gt=0)
    bottom_y_m: float = pydantic.Field(gt=0)
    bottom_height_m: float = pydantic.Field(ge=0)
    middle_x_m: float = pydantic.Field(gt=0)
    middle_y_m: float = pydantic.Field(gt=0)
    middle_height_m: float = pydantic.Field(ge=0)
    top_x_m: float = pydantic.Field(gt=0)
    top_y_m: float = pydantic.Field(gt=0)
    top_height_m: float = pydantic.Field(ge=0)
    vessel_height_m: float = pydantic.Field(gt=0)
    full_volume_m3: float = pydantic.Field(gt=0)
    rotation_deg: float = 0

    @pydantic.field_validator("rotation_deg")
    @classmethod
    def rotation_is_multiple_of_90(cls, value: float) -> float:
        if value % 90 != 0:
            raise ValueError("rotation_deg must be a multiple of 90")
        return value


class GeometrySensor(pydantic.BaseModel):
    """Позиция и наклон уровнемера (вкладка "Levelmeters" Конфигуратора).
    `tilt_x_deg`/`tilt_y_deg` — наклон луча визирования от истинной
    вертикали, уже разложенный Конфигуратором по осям X/Y самого бункера
    (incl_x/incl_y в UI Конфигуратора) — направление наклона полностью
    известно, в отличие от старого одиночного tilt_deg без азимута."""

    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    x: float
    y: float
    z: float
    tilt_x_deg: float
    tilt_y_deg: float


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
