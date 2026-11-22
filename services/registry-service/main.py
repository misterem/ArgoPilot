import sys

from fastapi import FastAPI

import config

try:
    config.get_settings()
except config.ConfigError as exc:
    sys.exit(f"registry-service: {exc}")

import catalogue  # noqa: E402
import farms  # noqa: E402
import plots  # noqa: E402
import problems  # noqa: E402

app = FastAPI(title="AgroPilot registry-service", version="0.1.0")
problems.install(app)
app.include_router(farms.router)
app.include_router(plots.router)
app.include_router(catalogue.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
