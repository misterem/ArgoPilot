"""Read-only catalogues. Only GET is registered, so other methods get 405."""

from collections.abc import Callable
from typing import Annotated, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, text
from db import get_db
from models import Crop, Emitter, Soil
from problems import ProblemError

router = APIRouter(prefix="/v1", tags=["catalogue"])

# table -> (response model, singular label for error messages)
CATALOGUES: dict[str, tuple[type[BaseModel], str]] = {
    "crops": (Crop, "Crop"),
    "soils": (Soil, "Soil"),
    "emitters": (Emitter, "Emitter"),
}


def _list_route(table: str, model: type[BaseModel]) -> Callable[..., Any]:
    sql = text(f"SELECT {', '.join(model.model_fields)} FROM {table}")

    def list_items(db: Annotated[Connection, Depends(get_db)]) -> list[dict]:
        # Sorted in Python so every backend orders by codepoint, like SQLite's BINARY collation.
        return sorted((dict(row) for row in db.execute(sql).mappings()), key=lambda item: item["id"])

    return list_items


def _get_route(table: str, model: type[BaseModel], label: str) -> Callable[..., Any]:
    sql = text(f"SELECT {', '.join(model.model_fields)} FROM {table} WHERE id = :id")

    def get_item(item_id: str, db: Annotated[Connection, Depends(get_db)]) -> dict:
        row = db.execute(sql, {"id": item_id}).mappings().first()
        if row is None:
            raise ProblemError(404, f"{label} {item_id} not found")
        return dict(row)

    return get_item


for _table, (_model, _label) in CATALOGUES.items():
    router.add_api_route(
        f"/{_table}", _list_route(_table, _model), methods=["GET"], response_model=list[_model]
    )
    router.add_api_route(
        f"/{_table}/{{item_id}}", _get_route(_table, _model, _label), methods=["GET"], response_model=_model
    )
