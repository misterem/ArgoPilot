"""One photo per plot, stored in S3 under {farm_id}/{plot_id}/photo; the key and content type live in plot_photos."""

import logging
from typing import Annotated

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

import config
from db import get_db
from models import PlotPhoto
from problems import ProblemError

logger = logging.getLogger("registry.photos")

router = APIRouter(prefix="/v1/plots", tags=["photos"])

Db = Annotated[Connection, Depends(get_db)]

MAX_BYTES = 5 * 1024 * 1024
CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp")


def _farm_id(db: Connection, plot_id: str) -> str:
    farm_id = db.execute(text("SELECT farm_id FROM plots WHERE id = :id"), {"id": plot_id}).scalar()
    if farm_id is None:
        raise ProblemError(404, f"Plot {plot_id} not found")
    return farm_id


def _s3():
    # Created per request, never at import time; boto3 finds the credentials itself.
    return boto3.client("s3", region_name=config.get_settings().aws_region)


@router.post("/{plot_id}/photo", status_code=201, response_model=PlotPhoto)
def upload_photo(plot_id: str, file: UploadFile, db: Db) -> dict:
    farm_id = _farm_id(db, plot_id)
    if file.content_type not in CONTENT_TYPES:
        raise ProblemError(422, f"file: content type must be one of {', '.join(CONTENT_TYPES)}")
    data = file.file.read(MAX_BYTES + 1)
    if not data:
        raise ProblemError(422, "file: must not be empty")
    if len(data) > MAX_BYTES:
        raise ProblemError(422, "file: must be at most 5 MB")

    key = f"{farm_id}/{plot_id}/photo"
    try:
        _s3().put_object(
            Bucket=config.get_settings().aws_s3_bucket, Key=key, Body=data, ContentType=file.content_type
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("S3 upload failed for %s", key)
        raise ProblemError(503, "Photo storage unavailable") from exc

    photo = {"plot_id": plot_id, "key": key, "content_type": file.content_type}
    try:
        db.execute(
            text(
                "INSERT INTO plot_photos (plot_id, key, content_type) VALUES (:plot_id, :key, :content_type) "
                "ON CONFLICT (plot_id) DO UPDATE SET key = excluded.key, content_type = excluded.content_type"
            ),
            photo,
        )
        db.commit()
    except IntegrityError as exc:
        # The plot was deleted between the lookup and the write.
        raise ProblemError(404, f"Plot {plot_id} not found") from exc
    return photo


@router.get("/{plot_id}/photo")
def download_photo(plot_id: str, db: Db) -> Response:
    _farm_id(db, plot_id)
    row = db.execute(
        text("SELECT key, content_type FROM plot_photos WHERE plot_id = :id"), {"id": plot_id}
    ).first()
    if row is None:
        raise ProblemError(404, f"Plot {plot_id} has no photo")

    try:
        obj = _s3().get_object(Bucket=config.get_settings().aws_s3_bucket, Key=row.key)
        with obj["Body"] as body:
            data = body.read()
    except (BotoCoreError, ClientError) as exc:
        logger.exception("S3 download failed for %s", row.key)
        raise ProblemError(503, "Photo storage unavailable") from exc
    return Response(content=data, media_type=row.content_type)
