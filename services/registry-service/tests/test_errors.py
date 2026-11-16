from conftest import assert_problem


def test_validation_problem_matches_spec_shape(client, plot_body):
    body = assert_problem(client.post("/v1/plots", json={**plot_body, "emitter_id": "nope"}), 422, "VALIDATION")
    assert body == {
        "type": "about:blank",
        "title": "Unprocessable Entity",
        "status": 422,
        "detail": "Unknown emitter",
        "code": "VALIDATION",
    }


def test_malformed_json_is_validation(client):
    response = client.post("/v1/farms", content="{not json", headers={"content-type": "application/json"})
    assert_problem(response, 422, "VALIDATION")


def test_unknown_route_is_not_found(client):
    assert_problem(client.get("/v1/nothing-here"), 404, "NOT_FOUND")


def test_missing_database_is_unavailable(client, monkeypatch, tmp_path):
    monkeypatch.setenv("REGISTRY_DB", str(tmp_path / "missing.db"))
    response = client.get("/v1/farms")
    assert_problem(response, 503, "UNAVAILABLE")
    assert response.headers["retry-after"].isdigit()
    assert not (tmp_path / "missing.db").exists()


def test_broken_database_is_unavailable(client, monkeypatch, tmp_path):
    empty = tmp_path / "empty.db"
    empty.touch()
    monkeypatch.setenv("REGISTRY_DB", str(empty))
    response = client.get("/v1/plots")
    assert_problem(response, 503, "UNAVAILABLE")
    assert "retry-after" in response.headers
