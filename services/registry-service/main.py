from fastapi import FastAPI
import catalogue
import farms
import plots
import problems

app = FastAPI(title="AgroPilot registry-service", version="0.1.0")
problems.install(app)
app.include_router(farms.router)
app.include_router(plots.router)
app.include_router(catalogue.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
