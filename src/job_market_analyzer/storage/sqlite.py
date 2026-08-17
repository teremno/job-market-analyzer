import sqlite3
from importlib import resources
from pathlib import Path

DatabasePath = str | Path


def load_schema() -> str:
    """Load the packaged SQLite schema."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "schema.sql"
    )

    return schema_file.read_text(encoding="utf-8")


def connect_database(
    database_path: DatabasePath,
) -> sqlite3.Connection:
    """
    Open a configured SQLite connection.

    The database path is provided by the caller so the storage layer
    does not depend on a specific machine, operating system, or
    filesystem layout.
    """

    connection = sqlite3.connect(str(database_path))

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    if str(database_path) != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")

    return connection


def initialize_database(
    connection: sqlite3.Connection,
) -> None:
    """Create the initial schema outside any active business transaction."""

    if connection.in_transaction:
        raise RuntimeError(
            "initialize_database must be called outside an active transaction"
        )

    try:
        connection.executescript(
            f"BEGIN IMMEDIATE;\n{load_schema()}\nCOMMIT;"
        )
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
