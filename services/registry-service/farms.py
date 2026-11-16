from typing import Annotated
from uuid import uuid4
from fastapi import APIRouter, Depends, Response
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from db import get_db
from models import Farm, FarmArea, FarmIn, FarmPatch
from problems import ProblemError

router = APIRouter(prefix="/v1/farms", tags=["farms"])

Db = Annotated[Connection, Depends(get_db)]


def _get_farm(db: Connection, farm_id: str) -> dict:
    row = db.execute(text("SELECT id, name FROM farms WHERE id = :id"), {"id": farm_id}).mappings().first()
    if row is None:
        raise ProblemError(404, f"Farm {farm_id} not found")
    return dict(row)


@router.post("", status_code=201, response_model=Farm)
def create_farm(body: FarmIn, db: Db) -> dict:
    farm = {"id": str(uuid4()), **body.model_dump()}
    db.execute(text("INSERT INTO farms (id, name) VALUES (:id, :name)"), farm)
    db.commit()
    return farm


@router.get("", response_model=list[Farm])
def list_farms(db: Db) -> list[dict]:
    # Sorted in Python so every backend orders by codepoint, like SQLite's BINARY collation.
    rows = db.execute(text("SELECT id, name FROM farms")).mappings()
    return sorted((dict(row) for row in rows), key=lambda farm: farm["name"])


@router.get("/{farm_id}", response_model=Farm)
def get_farm(farm_id: str, db: Db) -> dict:
    return _get_farm(db, farm_id)


@router.get("/{farm_id}/area", response_model=FarmArea)
def get_farm_area(farm_id: str, db: Db) -> dict:
    _get_farm(db, farm_id)
    row = db.execute(
        text("SELECT COALESCE(SUM(area_m2), 0.0) AS area_m2 FROM plots WHERE farm_id = :id"), {"id": farm_id}
    ).mappings().one()
    return dict(row)


@router.patch("/{farm_id}", response_model=Farm)
def update_farm(farm_id: str, body: FarmPatch, db: Db) -> dict:
    farm = _get_farm(db, farm_id)
    changes = body.changes()
    if changes:
        assignments = ", ".join(f"{column} = :{column}" for column in changes)
        db.execute(text(f"UPDATE farms SET {assignments} WHERE id = :id"), {**changes, "id": farm_id})
        db.commit()
    return {**farm, **changes}


@router.delete("/{farm_id}", status_code=204)
def delete_farm(farm_id: str, db: Db) -> Response:
    _get_farm(db, farm_id)
    has_plots = db.execute(text("SELECT 1 FROM plots WHERE farm_id = :id LIMIT 1"), {"id": farm_id}).first()
    if has_plots:
        raise ProblemError(409, "Farm still has plots; delete them first")
    try:
        db.execute(text("DELETE FROM farms WHERE id = :id"), {"id": farm_id})
        db.commit()
    except IntegrityError as exc:
        # A plot was added between the check and the delete.
        raise ProblemError(409, "Farm still has plots; delete them first") from exc
    return Response(status_code=204)
