from uuid import UUID

import pytest

from conftest import DEMO_FARM, EAST_FARM, assert_problem


def test_list_seeded_farms(client):
    response = client.get("/v1/farms")
    assert response.status_code == 200
    assert {f["name"] for f in response.json()} == {"Demo cooperative", "East farm"}


def test_create_get_patch_delete(client):
    created = client.post("/v1/farms", json={"name": "North farm"})
    assert created.status_code == 201
    farm = created.json()
    assert set(farm) == {"id", "name"}
    UUID(farm["id"])

    assert client.get(f"/v1/farms/{farm['id']}").json() == farm

    patched = client.patch(f"/v1/farms/{farm['id']}", json={"name": "Renamed"})
    assert patched.status_code == 200
    assert patched.json() == {"id": farm["id"], "name": "Renamed"}

    assert client.delete(f"/v1/farms/{farm['id']}").status_code == 204
    assert_problem(client.get(f"/v1/farms/{farm['id']}"), 404, "NOT_FOUND")


def test_empty_patch_changes_nothing(client):
    response = client.patch(f"/v1/farms/{EAST_FARM}", json={})
    assert response.json() == {"id": EAST_FARM, "name": "East farm"}


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": None}, {"name": "x", "id": "mine"}])
def test_create_rejects_bad_body(client, body):
    assert_problem(client.post("/v1/farms", json=body), 422, "VALIDATION")


@pytest.mark.parametrize("body", [{"name": ""}, {"name": None}])
def test_patch_rejects_bad_body(client, body):
    assert_problem(client.patch(f"/v1/farms/{DEMO_FARM}", json=body), 422, "VALIDATION")


def test_unknown_farm_is_404(client):
    missing = "00000000-0000-4000-8000-000000000000"
    assert_problem(client.get(f"/v1/farms/{missing}"), 404, "NOT_FOUND")
    assert_problem(client.patch(f"/v1/farms/{missing}", json={"name": "x"}), 404, "NOT_FOUND")
    assert_problem(client.delete(f"/v1/farms/{missing}"), 404, "NOT_FOUND")


def test_delete_farm_with_plots_is_conflict(client):
    assert_problem(client.delete(f"/v1/farms/{DEMO_FARM}"), 409, "CONFLICT")


def test_delete_farm_after_its_plots(client):
    for plot in client.get("/v1/plots", params={"farm_id": EAST_FARM}).json():
        assert client.delete(f"/v1/plots/{plot['id']}").status_code == 204
    assert client.delete(f"/v1/farms/{EAST_FARM}").status_code == 204


@pytest.mark.parametrize(("farm_id", "area"), [(DEMO_FARM, 1800), (EAST_FARM, 1900)])
def test_area_sums_the_farms_plots(client, farm_id, area):
    response = client.get(f"/v1/farms/{farm_id}/area")
    assert response.status_code == 200
    assert response.json() == {"area_m2": area}


def test_area_follows_plot_changes(client, plot_body):
    created = client.post("/v1/plots", json={**plot_body, "area_m2": 250.5}).json()
    assert client.get(f"/v1/farms/{DEMO_FARM}/area").json() == {"area_m2": 2050.5}

    client.patch(f"/v1/plots/{created['id']}", json={"farm_id": EAST_FARM})
    assert client.get(f"/v1/farms/{DEMO_FARM}/area").json() == {"area_m2": 1800}
    assert client.get(f"/v1/farms/{EAST_FARM}/area").json() == {"area_m2": 2150.5}


def test_area_of_farm_without_plots_is_zero(client):
    farm = client.post("/v1/farms", json={"name": "Empty farm"}).json()
    response = client.get(f"/v1/farms/{farm['id']}/area")
    assert response.status_code == 200
    assert response.json() == {"area_m2": 0}


def test_area_of_unknown_farm_is_404(client):
    missing = "00000000-0000-4000-8000-000000000000"
    assert_problem(client.get(f"/v1/farms/{missing}/area"), 404, "NOT_FOUND")


def test_area_without_database_is_503(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / "missing.db"}")
    response = client.get(f"/v1/farms/{DEMO_FARM}/area")
    assert_problem(response, 503, "UNAVAILABLE")
    assert "retry-after" in response.headers


def test_list_is_codepoint_ordered(client):
    for name in ("apple farm", "Zebra farm"):
        client.post("/v1/farms", json={"name": name})
    names = [f["name"] for f in client.get("/v1/farms").json()]
    assert names == sorted(names)
    assert names.index("Zebra farm") < names.index("apple farm")


def test_area_sum_is_identical_on_every_backend(client, plot_body):
    farm_id = client.post("/v1/farms", json={"name": "Float Farm"}).json()["id"]
    for index, area in enumerate((0.1, 0.2, 0.3)):
        body = {**plot_body, "name": f"p{index}", "farm_id": farm_id, "area_m2": area}
        assert client.post("/v1/plots", json=body).status_code == 201
    assert client.get(f"/v1/farms/{farm_id}/area").json() == {"area_m2": 0.6}
