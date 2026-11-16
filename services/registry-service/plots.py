from typing import Annotated, Any
from uuid import uuid4
from fastapi import APIRouter, Depends, Response
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from db import exists, get_db
from db_errors import is_unique_violation
from models import Plot, PlotIn, PlotPatch
from problems import ProblemError

router = APIRouter(prefix="/v1/plots", tags=["plots"])

Db = Annotated[Connection, Depends(get_db)]

COLUMNS = list(Plot.model_fields)
SELECT = f"SELECT {', '.join(COLUMNS)} FROM plots"

# body field -> (table it must exist in, label for the error message)
REFERENCES = {
    "farm_id": ("farms", "farm"),
    "crop_id": ("crops", "crop"),
    "soil_id": ("soils", "soil"),
    "emitter_id": ("emitters", "emitter"),
}


def _get_plot(db: Connection, plot_id: str) -> dict:
    row = db.execute(text(f"{SELECT} WHERE id = :id"), {"id": plot_id}).mappings().first()
    if row is None:
        raise ProblemError(404, f"Plot {plot_id} not found")
    return dict(row)


def _check_references(db: Connection, fields: dict[str, Any]) -> None:
    for field, (table, label) in REFERENCES.items():
        if field in fields and not exists(db, table, fields[field]):
            raise ProblemError(422, f"Unknown {label}")


def _write(db: Connection, sql: str, params: dict[str, Any]) -> None:
    try:
        db.execute(text(sql), params)
        db.commit()
    except IntegrityError as exc:
        # Don't reuse the connection after a failed write; closing it rolls back.
        if is_unique_violation(exc):
            raise ProblemError(409, "A plot with this name already exists on this farm") from exc
        raise


@router.post("", status_code=201, response_model=Plot)
def create_plot(body: PlotIn, db: Db) -> dict:
    plot = {"id": str(uuid4()), **body.model_dump(mode="json")}
    _check_references(db, plot)
    _write(
        db,
        f"INSERT INTO plots ({', '.join(COLUMNS)}) VALUES ({', '.join(':' + c for c in COLUMNS)})",
        plot,
    )
    return plot


@router.get("", response_model=list[Plot])
def list_plots(db: Db, farm_id: str | None = None) -> list[dict]:
    # Sorted in Python so every backend orders by codepoint, like SQLite's BINARY collation.
    if farm_id is None:
        rows = db.execute(text(SELECT)).mappings()
        return sorted((dict(row) for row in rows), key=lambda plot: (plot["farm_id"], plot["name"]))
    rows = db.execute(text(f"{SELECT} WHERE farm_id = :farm_id"), {"farm_id": farm_id}).mappings()
    return sorted((dict(row) for row in rows), key=lambda plot: plot["name"])


@router.get("/{plot_id}", response_model=Plot)
def get_plot(plot_id: str, db: Db) -> dict:
    return _get_plot(db, plot_id)


@router.patch("/{plot_id}", response_model=Plot)
def update_plot(plot_id: str, body: PlotPatch, db: Db) -> dict:
    plot = _get_plot(db, plot_id)
    changes = body.changes()
    if changes:
        _check_references(db, changes)
        assignments = ", ".join(f"{column} = :{column}" for column in changes)
        _write(db, f"UPDATE plots SET {assignments} WHERE id = :id", {**changes, "id": plot_id})
    return {**plot, **changes}


@router.delete("/{plot_id}", status_code=204)
def delete_plot(plot_id: str, db: Db) -> Response:
    _get_plot(db, plot_id)
    db.execute(text("DELETE FROM plots WHERE id = :id"), {"id": plot_id})
    db.commit()
    return Response(status_code=204)
