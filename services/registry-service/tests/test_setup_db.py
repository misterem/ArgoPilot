import importlib.util
import subprocess

from conftest import SERVICE_DIR

import config
import db
import schema

_spec = importlib.util.spec_from_file_location("setup_db", SERVICE_DIR / "scripts" / "setup_db.py")
setup_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup_db)


def test_setup_loads_schema_and_catalogue_only(tmp_path):
    path = tmp_path / "new.db"
    path.touch()
    assert setup_db.main(f"sqlite:///{path}") == 0
    with db.get_engine(f"sqlite:///{path}").connect() as conn:
        assert schema.existing_tables(conn) == sorted(schema.TABLES)
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM emitters").scalar() == 4
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM farms").scalar() == 0


def test_setup_refuses_when_tables_exist(tmp_path, capsys):
    path = tmp_path / "seeded.db"
    subprocess.run(["bash", str(SERVICE_DIR / "seed_registry.sh"), str(path)], check=True, capture_output=True)
    assert setup_db.main(f"sqlite:///{path}") == 1
    assert "Nothing changed" in capsys.readouterr().err


def test_setup_without_config_exits_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "absent.env")
    config.get_settings.cache_clear()
    assert setup_db.main() == 2
    assert "DATABASE_URL is not set" in capsys.readouterr().err
