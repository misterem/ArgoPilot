from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from db import SERVICE_DIR

TABLES = ("farms", "crops", "soils", "emitters", "plots")


def statements(filename: str) -> list[str]:
    pieces = (SERVICE_DIR / filename).read_text().split(";")
    return [piece.strip() for piece in pieces if piece.strip()]


def existing_tables(conn: Connection) -> list[str]:
    return sorted(set(inspect(conn).get_table_names()) & set(TABLES))


def load(conn: Connection, *filenames: str) -> None:
    for filename in filenames:
        for statement in statements(filename):
            conn.exec_driver_sql(statement)
