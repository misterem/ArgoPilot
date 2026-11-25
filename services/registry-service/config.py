"""Service settings, read from the environment or `.env` in this folder (a real environment variable wins)."""

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

    database_url: str = Field(min_length=1)
    aws_s3_bucket: str = Field(min_length=1)
    aws_region: str = Field(min_length=1)


def load_settings(env_file: Path | None) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        names = sorted({str(err["loc"][0]).upper() for err in exc.errors()})
        verb = "is" if len(names) == 1 else "are"
        raise ConfigError(
            f"{', '.join(names)} {verb} not set. Copy .env.example to .env in services/registry-service, "
            "or set it in the environment."
        ) from None


@functools.cache
def get_settings() -> Settings:
    return load_settings(ENV_FILE)
