import re
from datetime import date
from typing import Annotated, Any, Self
from uuid import UUID
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def _iso_date_string(value: Any) -> Any:
    # Without this, pydantic also accepts Unix timestamps and datetime strings.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("must be a YYYY-MM-DD string")
    return value


def _not_in_future(value: date) -> date:
    if value > date.today():
        raise ValueError("must not be in the future")
    return value


Name = Annotated[str, Field(min_length=1)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Lat = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Lon = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
PlantingDate = Annotated[date, BeforeValidator(_iso_date_string), AfterValidator(_not_in_future)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Patch(Input):
    """All fields optional; a field that is sent must not be null."""

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        nulls = sorted(f for f in self.model_fields_set if getattr(self, f) is None)
        if nulls:
            raise ValueError(f"{', '.join(nulls)} cannot be null")
        return self

    def changes(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True)


class FarmIn(Input):
    name: Name


class FarmPatch(Patch):
    name: Name | None = None


class Farm(BaseModel):
    id: str
    name: str


class FarmArea(BaseModel):
    area_m2: float


class PlotIn(Input):
    farm_id: UUID
    name: Name
    area_m2: Positive
    crop_id: str
    planting_date: PlantingDate
    soil_id: str
    row_spacing_m: Positive
    emitter_spacing_m: Positive
    emitter_id: str
    lat: Lat
    lon: Lon


class PlotPatch(Patch):
    farm_id: UUID | None = None
    name: Name | None = None
    area_m2: Positive | None = None
    crop_id: str | None = None
    planting_date: PlantingDate | None = None
    soil_id: str | None = None
    row_spacing_m: Positive | None = None
    emitter_spacing_m: Positive | None = None
    emitter_id: str | None = None
    lat: Lat | None = None
    lon: Lon | None = None


class Plot(BaseModel):
    id: str
    farm_id: str
    name: str
    area_m2: float
    crop_id: str
    planting_date: date
    soil_id: str
    row_spacing_m: float
    emitter_spacing_m: float
    emitter_id: str
    lat: float
    lon: float


class PlotPhoto(BaseModel):
    plot_id: str
    key: str
    content_type: str


class Crop(BaseModel):
    id: str
    name: str


class Soil(BaseModel):
    id: str
    name: str
    available_water_mm_per_m: int


class Emitter(BaseModel):
    id: str
    name: str
    flow_lph: float
