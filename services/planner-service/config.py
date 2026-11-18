"""Service settings, read from the environment or `.env` in this folder (a real environment variable wins).

Every variable is required; see .env.example.
"""

import functools
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).parent
ENV_FILE = SERVICE_DIR / ".env"


class ConfigError(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    registry_url: str = Field(min_length=1)
    weather_url: str = Field(min_length=1)
    registry_timeout_s: float = Field(gt=0)
    # Must exceed weather-service's worst case (~16 s with its example settings).
    weather_timeout_s: float = Field(gt=0)

    @field_validator("registry_url", "weather_url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be an http:// or https:// URL with a host")
        return value


def load_settings(env_file: Path | None) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        missing, invalid = [], []
        for err in exc.errors():
            if not err["loc"]:  # a rule across fields
                invalid.append(err["msg"].removeprefix("Value error, "))
                continue
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
            "; ".join(parts) + ". Copy .env.example to .env in services/planner-service, or set it in the environment."
        ) from None


@functools.cache
def get_settings() -> Settings:
    return load_settings(ENV_FILE)
