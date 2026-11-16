from conftest import NORTH_BLOCK, SERVICE_DIR


def test_schema_file_uses_double_precision():
    sql = (SERVICE_DIR / "schema.sql").read_text()
    assert "REAL" not in sql.replace("DOUBLE PRECISION", "")
    assert "UNIQUE (farm_id, name)" in sql


def test_seed_keeps_float_values(client):
    assert client.get("/v1/emitters/dripnet-pc-0.6").json()["flow_lph"] == 0.6
    assert client.get(f"/v1/plots/{NORTH_BLOCK}").json()["lat"] == 31.25
