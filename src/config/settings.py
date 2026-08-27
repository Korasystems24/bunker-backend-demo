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


class BuildupSettings(pydantic.BaseModel):
    """Параметры эвристики налипания v1 (пороги меняются без правки кода)."""

    outer_position_threshold: int = 6
    deviation_threshold_m: float = 0.35


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
    buildup: BuildupSettings = pydantic.Field(default_factory=BuildupSettings)
    logging: LoggingSettings = pydantic.Field(default_factory=LoggingSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
