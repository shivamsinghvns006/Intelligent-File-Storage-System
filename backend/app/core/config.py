"""Validated server-only configuration for the Milestone 1 skeleton."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security_policy import resolve_allowed_origins, safe_configuration_error_fields

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings read from process environment, with ignored root .env for local use."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_allowed_origins: str | None = None
    cors_allow_credentials: bool = True

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowlist(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return value
        resolve_allowed_origins("development", value, allow_credentials=True)
        return value

    @model_validator(mode="after")
    def validate_environment_policy(self) -> "Settings":
        origins = resolve_allowed_origins(
            self.app_env,
            self.cors_allowed_origins,
            self.cors_allow_credentials,
        )
        self.cors_allowed_origins = ",".join(origins)
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return list(
            resolve_allowed_origins(
                self.app_env,
                self.cors_allowed_origins,
                self.cors_allow_credentials,
            )
        )


def configuration_error_fields(error: ValidationError) -> str:
    """Return field names only; Pydantic error input/context is deliberately omitted."""
    return safe_configuration_error_fields(item["loc"] for item in error.errors())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
