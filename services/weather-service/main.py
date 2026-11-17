import sys

from fastapi import FastAPI

import config

try:
    config.get_settings()
except config.ConfigError as exc:
    sys.exit(f"weather-service: {exc}")

import problems  # noqa: E402

app = FastAPI(title="AgroPilot weather-service", version="0.1.0")
problems.install(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
