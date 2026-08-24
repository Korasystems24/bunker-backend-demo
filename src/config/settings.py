"""Конфигурация приложения: pydantic-settings с вложенными секциями.

Переменные окружения: префикс BUNKER_, вложенность через '__'.
Пример: BUNKER_DATABASE__URL=postgresql+asyncpg://...
"""

from functools import lru_cache

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
        default_factory=lambda: ["http://localhost:5173"],
    )
    # Токен edge-устройств для POST-ручек (X-API-Key), шаг 2 плана.
    edge_api_key: str = "change-me-edge-token"


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
    api: ApiSettings = pydantic.Field(default_factory=ApiSettings)
    logging: LoggingSettings = pydantic.Field(default_factory=LoggingSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
