import pytest

from conftest import assert_problem


def test_crops(client):
    assert client.get("/v1/crops").json() == [
        {"id": "bell-pepper", "name": "Bell pepper"},
        {"id": "tomato", "name": "Tomato"},
    ]
    assert client.get("/v1/crops/tomato").json() == {"id": "tomato", "name": "Tomato"}


def test_soils(client):
    assert len(client.get("/v1/soils").json()) == 3
    assert client.get("/v1/soils/sand").json() == {"id": "sand", "name": "Sand", "available_water_mm_per_m": 83}


def test_emitters(client):
    assert len(client.get("/v1/emitters").json()) == 4
    assert client.get("/v1/emitters/dripnet-pc-1.0").json() == {
        "id": "dripnet-pc-1.0",
        "name": "DripNet PC",
        "flow_lph": 1.0,
    }


@pytest.mark.parametrize("table", ["crops", "soils", "emitters"])
def test_unknown_id_is_404(client, table):
    assert_problem(client.get(f"/v1/{table}/nope"), 404, "NOT_FOUND")


@pytest.mark.parametrize("path", ["/v1/crops", "/v1/soils/sand", "/v1/emitters/dripnet-pc-1.0"])
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_catalogues_are_read_only(client, method, path):
    response = client.request(method, path, json={})
    assert_problem(response, 405, "VALIDATION")
    assert response.headers["allow"] == "GET"
