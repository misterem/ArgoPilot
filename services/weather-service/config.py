"""Service settings, read from the environment or `.env` in this folder (a real environment variable wins).

Every variable is required; see .env.example.
"""

import functools
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).parent
ENV_FILE = SERVICE_DIR / ".env"


class ConfigError(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    provider_base_url: str = Field(min_length=1)
    provider_api_key: str  # required, may be empty (Open-Meteo's free tier needs no key)
    provider_timeout_s: float = Field(gt=0)
    provider_retries: int = Field(ge=0)
    provider_retry_backoff_s: float = Field(ge=0)
    forecast_fresh_hours: float = Field(gt=0)
    forecast_max_stale_hours: float = Field(gt=0)
    retry_after_s: int = Field(gt=0)


def load_settings(env_file: Path | None) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        missing, invalid = [], []
        for err in exc.errors():
            name = str(err["loc"][0]).upper()
            if err["type"] == "missing" or (err["type"] == "string_too_short" and err.get("input") == ""):
                missing.append(name)
            else:
                invalid.append(f"{name} is invalid: {err['msg']}")
        parts = []
        if missing:
            verb = "is" if len(missing) == 1 else "are"
            parts.append(f"{', '.join(missing)} {verb} not set")
        parts.extend(invalid)
        raise ConfigError(
            "; ".join(parts) + ". Copy .env.example to .env in services/weather-service, or set it in the environment."
        ) from None


@functools.cache
def get_settings() -> Settings:
    return load_settings(ENV_FILE)
