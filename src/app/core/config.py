"""Application settings loaded exclusively from environment variables (or a local .env file)."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def _split_comma(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CommaSeparated = Annotated[list[str], NoDecode, BeforeValidator(_split_comma)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Investment Calculation API"
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)

    cors_origins: CommaSeparated = []
    log_level: LogLevel = LogLevel.INFO

    api_key: SecretStr | None = None

    max_series_length: int = Field(default=100_000, ge=1)
    max_monte_carlo_cells: int = Field(default=10_000_000, ge=1)

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_api_key_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_in_production(cls, value: list[str], info: Any) -> list[str]:
        if "*" in value and info.data.get("app_env") == AppEnv.PRODUCTION:
            raise ValueError("CORS_ORIGINS cannot contain '*' when APP_ENV=production")
        return value

    @property
    def auth_enabled(self) -> bool:
        return self.api_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
