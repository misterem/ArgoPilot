import sqlite3
from typing import Annotated
from uuid import uuid4
from fastapi import APIRouter, Depends, Response
from db import get_db
from models import Farm, FarmArea, FarmIn, FarmPatch
from problems import ProblemError

router = APIRouter(prefix="/v1/farms", tags=["farms"])

Db = Annotated[sqlite3.Connection, Depends(get_db)]


def _get_farm(db: sqlite3.Connection, farm_id: str) -> dict:
    row = db.execute("SELECT id, name FROM farms WHERE id = ?", (farm_id,)).fetchone()
    if row is None:
        raise ProblemError(404, f"Farm {farm_id} not found")
    return dict(row)


@router.post("", status_code=201, response_model=Farm)
def create_farm(body: FarmIn, db: Db) -> dict:
    farm = {"id": str(uuid4()), **body.model_dump()}
    with db:
        db.execute("INSERT INTO farms (id, name) VALUES (:id, :name)", farm)
    return farm


@router.get("", response_model=list[Farm])
def list_farms(db: Db) -> list[dict]:
    return [dict(row) for row in db.execute("SELECT id, name FROM farms ORDER BY name")]


@router.get("/{farm_id}", response_model=Farm)
def get_farm(farm_id: str, db: Db) -> dict:
    return _get_farm(db, farm_id)


@router.get("/{farm_id}/area", response_model=FarmArea)
def get_farm_area(farm_id: str, db: Db) -> dict:
    _get_farm(db, farm_id)
    row = db.execute("SELECT TOTAL(area_m2) AS area_m2 FROM plots WHERE farm_id = ?", (farm_id,)).fetchone()
    return dict(row)


@router.patch("/{farm_id}", response_model=Farm)
def update_farm(farm_id: str, body: FarmPatch, db: Db) -> dict:
    farm = _get_farm(db, farm_id)
    changes = body.changes()
    if changes:
        assignments = ", ".join(f"{column} = :{column}" for column in changes)
        with db:
            db.execute(f"UPDATE farms SET {assignments} WHERE id = :id", {**changes, "id": farm_id})
    return {**farm, **changes}


@router.delete("/{farm_id}", status_code=204)
def delete_farm(farm_id: str, db: Db) -> Response:
    _get_farm(db, farm_id)
    has_plots = db.execute("SELECT 1 FROM plots WHERE farm_id = ? LIMIT 1", (farm_id,)).fetchone()
    if has_plots:
        raise ProblemError(409, "Farm still has plots; delete them first")
    try:
        with db:
            db.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
    except sqlite3.IntegrityError as exc:
        # A plot was added between the check and the delete.
        raise ProblemError(409, "Farm still has plots; delete them first") from exc
    return Response(status_code=204)
