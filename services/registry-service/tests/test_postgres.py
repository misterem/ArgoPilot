import pytest

import db
from conftest import TEST_POSTGRES_URL, assert_problem, requires_postgres

pytestmark = [requires_postgres, pytest.mark.parametrize("client", ["postgres"], indirect=True)]


def test_missing_tables_is_unavailable(client):
    with db.get_engine(db.engine_url(TEST_POSTGRES_URL)).begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")
    response = client.get("/v1/plots")
    assert_problem(response, 503, "UNAVAILABLE")
    assert "retry-after" in response.headers


def test_connection_is_clean_after_conflict(client, plot_body):
    assert client.post("/v1/plots", json=plot_body).status_code == 201
    assert_problem(client.post("/v1/plots", json=plot_body), 409, "CONFLICT")
    assert client.get("/v1/plots").status_code == 200
