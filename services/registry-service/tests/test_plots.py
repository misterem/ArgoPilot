from datetime import date, timedelta
from uuid import UUID

import pytest

from conftest import DEMO_FARM, EAST_FARM, NORTH_BLOCK, assert_problem

PLOT_FIELDS = {
    "id", "farm_id", "name", "area_m2", "crop_id", "planting_date", "soil_id",
    "row_spacing_m", "emitter_spacing_m", "emitter_id", "lat", "lon",
}


def test_create_returns_body_plus_id(client, plot_body):
    response = client.post("/v1/plots", json=plot_body)
    assert response.status_code == 201
    plot = response.json()
    UUID(plot.pop("id"))
    assert plot == plot_body


def test_get_returns_only_listed_fields(client):
    plot = client.get(f"/v1/plots/{NORTH_BLOCK}").json()
    assert set(plot) == PLOT_FIELDS
    assert plot["name"] == "North block"
    assert plot["planting_date"] == "2026-03-01"


def test_list_all_and_by_farm(client):
    assert len(client.get("/v1/plots").json()) == 4
    demo = client.get("/v1/plots", params={"farm_id": DEMO_FARM}).json()
    assert {p["name"] for p in demo} == {"North block", "East block"}
    assert all(p["farm_id"] == DEMO_FARM for p in demo)


def test_list_with_no_rows_is_empty_array(client):
    farm = client.post("/v1/farms", json={"name": "Empty"}).json()
    response = client.get("/v1/plots", params={"farm_id": farm["id"]})
    assert response.status_code == 200
    assert response.json() == []


def test_patch_changes_only_sent_fields(client):
    before = client.get(f"/v1/plots/{NORTH_BLOCK}").json()
    response = client.patch(f"/v1/plots/{NORTH_BLOCK}", json={"area_m2": 1200, "soil_id": "sand"})
    assert response.status_code == 200
    assert response.json() == {**before, "area_m2": 1200, "soil_id": "sand"}
    assert client.get(f"/v1/plots/{NORTH_BLOCK}").json() == response.json()


def test_delete_plot(client):
    assert client.delete(f"/v1/plots/{NORTH_BLOCK}").status_code == 204
    assert_problem(client.get(f"/v1/plots/{NORTH_BLOCK}"), 404, "NOT_FOUND")
    assert_problem(client.delete(f"/v1/plots/{NORTH_BLOCK}"), 404, "NOT_FOUND")


TOMORROW = (date.today() + timedelta(days=1)).isoformat()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("area_m2", 0),
        ("area_m2", -5),
        ("row_spacing_m", 0),
        ("emitter_spacing_m", -0.1),
        ("planting_date", TOMORROW),
        ("planting_date", "01/03/2026"),
        ("planting_date", 1772323200),
        ("lat", 90.1),
        ("lat", -90.1),
        ("lon", 180.1),
        ("lon", -180.1),
        ("name", ""),
        ("farm_id", "not-a-uuid"),
    ],
)
def test_create_rejects_bad_field(client, plot_body, field, value):
    body = assert_problem(client.post("/v1/plots", json={**plot_body, field: value}), 422, "VALIDATION")
    assert field in body["detail"]


@pytest.mark.parametrize(("field", "value"), [("lat", 90), ("lat", -90), ("lon", 180), ("lon", -180)])
def test_coordinate_bounds_are_inclusive(client, plot_body, field, value):
    assert client.post("/v1/plots", json={**plot_body, field: value}).status_code == 201


def test_planting_today_is_allowed(client, plot_body):
    response = client.post("/v1/plots", json={**plot_body, "planting_date": date.today().isoformat()})
    assert response.status_code == 201


@pytest.mark.parametrize("field", sorted(PLOT_FIELDS - {"id"}))
def test_create_requires_every_field(client, plot_body, field):
    del plot_body[field]
    assert_problem(client.post("/v1/plots", json=plot_body), 422, "VALIDATION")


@pytest.mark.parametrize(
    ("field", "detail"),
    [("crop_id", "Unknown crop"), ("soil_id", "Unknown soil"), ("emitter_id", "Unknown emitter")],
)
def test_unknown_catalogue_entry(client, plot_body, field, detail):
    body = assert_problem(client.post("/v1/plots", json={**plot_body, field: "nope"}), 422, "VALIDATION")
    assert body["detail"] == detail
    body = assert_problem(client.patch(f"/v1/plots/{NORTH_BLOCK}", json={field: "nope"}), 422, "VALIDATION")
    assert body["detail"] == detail


def test_unknown_farm(client, plot_body):
    missing = "00000000-0000-4000-8000-000000000000"
    body = assert_problem(client.post("/v1/plots", json={**plot_body, "farm_id": missing}), 422, "VALIDATION")
    assert body["detail"] == "Unknown farm"


def test_patch_validates_fields(client):
    assert_problem(client.patch(f"/v1/plots/{NORTH_BLOCK}", json={"area_m2": 0}), 422, "VALIDATION")
    assert_problem(client.patch(f"/v1/plots/{NORTH_BLOCK}", json={"planting_date": TOMORROW}), 422, "VALIDATION")
    assert_problem(client.patch(f"/v1/plots/{NORTH_BLOCK}", json={"lat": None}), 422, "VALIDATION")
    assert_problem(client.patch(f"/v1/plots/{NORTH_BLOCK}", json={"id": "x"}), 422, "VALIDATION")


def test_duplicate_name_on_same_farm_is_conflict(client, plot_body):
    assert_problem(client.post("/v1/plots", json={**plot_body, "name": "North block"}), 409, "CONFLICT")
    assert_problem(client.patch(f"/v1/plots/{NORTH_BLOCK}", json={"name": "East block"}), 409, "CONFLICT")


def test_same_name_on_another_farm_is_allowed(client, plot_body):
    response = client.post("/v1/plots", json={**plot_body, "farm_id": EAST_FARM, "name": "North block"})
    assert response.status_code == 201


def test_unknown_plot_is_404(client):
    assert_problem(client.get("/v1/plots/nope"), 404, "NOT_FOUND")
    assert_problem(client.patch("/v1/plots/nope", json={"name": "x"}), 404, "NOT_FOUND")
