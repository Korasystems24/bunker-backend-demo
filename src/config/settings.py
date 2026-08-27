"""Конфигурация приложения: pydantic-settings с вложенными секциями.

Переменные окружения: префикс BUNKER_, вложенность через '__'.
Пример: BUNKER_DATABASE__URL=postgresql+asyncpg://...
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import pydantic
import pydantic_settings


class DatabaseSettings(pydantic.BaseModel):
    url: str = "postgresql+asyncpg://bunker:bunker@localhost:5432/bunker"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class ApiSettings(pydantic.BaseModel):
    # Явный allowlist origin'ов фронта; '*' не используется.
    cors_origins: list[str] = pydantic.Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )
    # Bearer-токен edge-устройств для POST-ручек (Authorization: Bearer),
    # как шлёт агент EdgePC. Значение должно совпадать с DISPATCH__HTTP__AUTH_TOKEN.
    edge_auth_token: str = "change-me-edge-token"
    # Порог тишины узла: нет telemetry/events/health дольше этого — offline.
    edge_stale_after_sec: int = 300
    silence_poll_interval_sec: int = 30
    edge_clock_drift_warn_sec: int = 60


class BuildupSettings(pydantic.BaseModel):
    """Параметры эвристики налипания v1 (пороги меняются без правки кода)."""

    outer_position_threshold: int = 6
    deviation_threshold_m: float = 0.35


class CatalogSettings(pydantic.BaseModel):
    path: Path = Path("catalog/bunkers.json")


class LoggingSettings(pydantic.BaseModel):
    level: str = "INFO"
    json_logs: bool = False


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="BUNKER_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database: DatabaseSettings = pydantic.Field(default_factory=DatabaseSettings)
    environment: Literal["development", "test", "production"] = "development"
    api: ApiSettings = pydantic.Field(default_factory=ApiSettings)
    buildup: BuildupSettings = pydantic.Field(default_factory=BuildupSettings)
    catalog: CatalogSettings = pydantic.Field(default_factory=CatalogSettings)
    logging: LoggingSettings = pydantic.Field(default_factory=LoggingSettings)

    @pydantic.model_validator(mode="after")
    def reject_default_production_token(self) -> Self:
        if self.environment == "production" and self.api.edge_auth_token == "change-me-edge-token":
            raise ValueError("production requires an explicit BUNKER_API__EDGE_AUTH_TOKEN")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
