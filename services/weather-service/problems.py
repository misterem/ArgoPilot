"""RFC 9457 problem+json responses for every error the API returns."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODES = {
    404: "NOT_FOUND",
    405: "VALIDATION",
    422: "VALIDATION",
    503: "UNAVAILABLE",
}

# Pinned because Python 3.13 renamed 422 to "Unprocessable Content".
TITLES = {422: "Unprocessable Entity"}


class ProblemError(Exception):
    def __init__(self, status: int, detail: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.headers = headers


def problem(status: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": TITLES.get(status, HTTPStatus(status).phrase),
        "status": status,
        "detail": detail,
        "code": CODES.get(status, "VALIDATION" if status < 500 else "UNAVAILABLE"),
    }
    return JSONResponse(body, status_code=status, headers=headers, media_type="application/problem+json")


def _describe(errors: list[dict]) -> str:
    parts = []
    for err in errors:
        loc = list(err["loc"])
        if loc and loc[0] in ("body", "query", "path"):
            loc = loc[1:]
        field = ".".join(str(part) for part in loc)
        parts.append(f"{field}: {err['msg']}" if field else err["msg"])
    return "; ".join(parts)


def install(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(_: Request, exc: ProblemError) -> JSONResponse:
        return problem(exc.status, exc.detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(422, _describe(exc.errors()))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail), exc.headers)
