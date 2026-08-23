"""Validated database configuration and per-request read-only connections."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from job_market_analyzer.analytics import SQLiteAnalyticsRepository
from job_market_analyzer.storage.sqlite import (
    CURRENT_SCHEMA_VERSION,
    DatabaseSchemaError,
    connect_read_only_database,
    initialize_database,
)


class DatabaseConfigurationError(RuntimeError):
    """The selected database cannot safely serve the local API."""


class DatabaseUnavailableError(RuntimeError):
    """A previously validated database is unavailable during a request."""


@dataclass(frozen=True, slots=True)
class ApiDatabaseSession:
    """One request's caller-owned read connection and analytics repository."""

    connection: sqlite3.Connection
    analytics: SQLiteAnalyticsRepository


def validate_database_path(database_path: Path) -> Path:
    """Resolve and structurally validate an existing current-schema database."""

    try:
        resolved_path = database_path.resolve(strict=True)
        if not resolved_path.is_file():
            raise FileNotFoundError
        with closing(connect_read_only_database(resolved_path)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version != CURRENT_SCHEMA_VERSION:
                raise DatabaseConfigurationError(
                    f"Database schema version {CURRENT_SCHEMA_VERSION} is required."
                )
            initialize_database(connection)
    except DatabaseConfigurationError:
        raise
    except (
        DatabaseSchemaError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        sqlite3.Error,
    ) as exc:
        raise DatabaseConfigurationError(
            "Existing readable SQLite database with the current schema is required."
        ) from exc
    return resolved_path


def get_database_session(request: Request) -> Iterator[ApiDatabaseSession]:
    """Yield one read-only SQLite connection and close it after the request."""

    connection: sqlite3.Connection | None = None
    try:
        connection = connect_read_only_database(request.app.state.database_path)
        yield ApiDatabaseSession(
            connection=connection,
            analytics=SQLiteAnalyticsRepository(
                connection,
                now_provider=getattr(
                    request.app.state, "analytics_now_provider", None
                ),
            ),
        )
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseUnavailableError("The analytics database is unavailable.") from exc
    except RuntimeError as exc:
        # Route-level errors (for example ApiNotFoundError) propagate through
        # this generator during teardown; only schema/runtime storage failures
        # map to the 503 envelope.
        if isinstance(exc, DatabaseSchemaError):
            raise DatabaseUnavailableError(
                "The analytics database is unavailable."
            ) from exc
        raise
    finally:
        if connection is not None:
            connection.close()
