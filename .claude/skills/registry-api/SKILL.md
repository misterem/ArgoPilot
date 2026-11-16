---
name: registry-api
description: AgroPilot's API conventions for registry-service — /v1 routes, list shapes, spec-only response fields, PATCH semantics, RFC 9457 problem+json errors with stable codes, required tests, and when to stop and ask. Use this whenever you add, change, rename or remove an endpoint, route, query parameter, request/response model, status code or error in services/registry-service (farms.py, plots.py, catalogue.py, models.py, problems.py, main.py), and when writing tests for one — even for a "small" tweak like a new filter, a new field, or a different error status.
---

# registry-api conventions

These rules keep registry-service predictable for its clients: every endpoint looks and fails the same way, and nothing ships that the spec didn't ask for. They apply to new endpoints and to changes to existing ones. Most of the machinery already exists, so the job is usually to plug into it rather than build anything new.

## 1. Routes live under `/v1`

Give each router its prefix: `APIRouter(prefix="/v1/<resource>", tags=[...])`, and include it in `main.py`. A client that pins `/v1` must never see a route move or change shape under it. (`/health` is the one route outside `/v1`; it's a liveness probe, not part of the API. Leave it as is.)

## 2. Lists are bare JSON arrays; no rows is `200 []`

Declare `response_model=list[Model]` and return a list. No `{"items": ...}` envelope, no `count`, no pagination unless the spec asks for it.

An empty result is a successful query, not an error: `200` with `[]`. That includes a filter that matches nothing, such as `GET /v1/plots?farm_id=<farm that doesn't exist>` (this was decided in `docs/judgment-log.md`; read it before deciding a similar case).

## 3. Return only the fields the spec lists

Response models in `models.py` hold exactly the spec'd fields, and SQL column lists are built from them (`list(Plot.model_fields)`), so the model is the single source of truth. Don't add fields the spec doesn't list: no `created_at`, no `links`, no computed extras, no "helpful" nested objects. Each extra field is a promise to clients that nobody agreed to make.

If the response needs a field that isn't stored yet, the schema lives in `schema.sql` (there are no migrations; SQLite loads it via `seed_registry.sh`, Postgres via `scripts/setup_db.py`). Change `schema.sql` and the matching models together.

If the spec doesn't list the fields for a response, ask (rule 8).

## 4. PATCH changes only the fields in the body

Make the body model subclass `models.Patch`: every field optional, explicit `null` rejected with 422, unknown fields rejected by `extra="forbid"`. Use `body.changes()`, which returns only the fields that were sent, to build the `UPDATE`, and return `{**current, **changes}`. Fields the client didn't send are left alone, not reset to defaults. Run any existence checks (`_check_references` in `plots.py`) on the changed fields too.

## 5. Every error is problem+json with a stable `code`

Raise `ProblemError(status, detail)` from `problems.py`. `problems.install(app)` already turns that, `RequestValidationError`, Starlette 404/405 and SQLAlchemy `DBAPIError` (via `db_errors.is_unavailable`) into RFC 9457 responses:

| Status | `code` | Typical cause |
| --- | --- | --- |
| 422 | `VALIDATION` | Bad/missing field, unknown referenced id (`Unknown farm`), malformed JSON |
| 404 | `NOT_FOUND` | Unknown id in the path, unknown route |
| 409 | `CONFLICT` | UNIQUE violation, deleting something that still has children |
| 503 | `UNAVAILABLE` | Database missing or unreadable; `Retry-After` is added automatically |

405 also maps to `VALIDATION` (writes to read-only catalogue routes).

What this means in practice:
- Never use `fastapi.HTTPException(detail=...)`, return a hand-built `JSONResponse`, or return an error dict. Those produce FastAPI's default `{"detail": ...}` body or bypass the content type. `ProblemError` is the only way to fail.
- Keep `detail` a short human sentence ("Plot {id} not found"). The `code` is what clients branch on, so don't invent new codes or change existing ones.
- Field rules (ranges, formats, required) belong in the pydantic models. Rules that need the database (does this crop exist? is this name taken?) belong in the route module. A DB-level constraint becomes a `ProblemError` by catching `sqlalchemy.exc.IntegrityError` and checking `db_errors.is_unique_violation` (see `_write` in `plots.py`).
- A body field pointing at a row that doesn't exist is 422 `Unknown <thing>`, not 404, because the URL itself exists (judgment log).

## 6. Every endpoint gets tests: success and every failure it can return

Tests go in `tests/test_<resource>.py` and use the `client` fixture (a freshly seeded DB per test) and the seed constants in `tests/conftest.py`. Check every error with `assert_problem(response, status, code)`, which also checks the content type and body shape. That's how "never FastAPI's default body" gets enforced.

Before writing tests, list the outcomes the endpoint can produce, then write at least one test per item:
- **Success**: status, exact body (compare against the request or a re-fetch), and for lists the exact field set (`set(item) == FIELDS`).
- **Empty list** for list endpoints: `200` and `[]`.
- **422** for each field rule (parametrize: missing, wrong type, out of range, null on PATCH, extra field) and for each unknown reference.
- **404** for an unknown path id.
- **409** for each conflict the endpoint can hit.
- **503** with a missing database (`monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing_path}")`) and a `retry-after` header. Every route that touches the DB can return it.
- **PATCH**: unsent fields unchanged, and the change persisted (GET it again).

When you change an existing endpoint, update its existing tests too. Don't just add new ones next to stale ones.

## 7. Run the tests before saying it's done

From `services/registry-service`:

```bash
uv run pytest
```

Run the whole suite, not only the new tests, because shared pieces like `problems.py` and the models affect every route. Report the actual result. If anything fails, fix it or say plainly what's failing. "Done" means the suite passed in this session.

If the change adds or changes routes or error cases, update the API and error tables in `services/registry-service/README.md` to match.

## 8. If the spec doesn't say, ask

Don't invent behavior to fill a gap. Spec gaps look like: an outcome with no status given (unknown parent on a nested route: `404` or `200 []`?), a field list that isn't spelled out, uniqueness or case sensitivity, ordering, what happens to children on delete, whether a filter value is validated.

When you find one:
1. Check `docs/judgment-log.md` first. If an entry already settles a case of the same shape, follow it and say which entry you followed.
2. Otherwise stop and ask the user before implementing that part. Name the case, give the options, and say which one you'd suggest and why. You can carry on with the parts the spec does cover.
3. Add an entry to `docs/judgment-log.md` in its existing format: a `##` heading for the case and an **Agent suggested:** line. Leave **Decided:** and **Why:** for the user to fill in.
