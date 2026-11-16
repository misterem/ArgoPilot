from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError, ProgrammingError

UNIQUE_VIOLATION = "23505"
UNDEFINED_TABLE = "42P01"


def is_unique_violation(exc: IntegrityError) -> bool:
    # Postgres exposes SQLSTATE; sqlite3 only has the message text.
    return getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION or "UNIQUE" in str(exc.orig)


def is_unavailable(exc: DBAPIError) -> bool:
    if isinstance(exc, (OperationalError, InterfaceError)) or exc.connection_invalidated:
        return True
    # A missing table means the schema was never loaded: an outage, not a client error.
    return isinstance(exc, ProgrammingError) and getattr(exc.orig, "sqlstate", None) == UNDEFINED_TABLE
