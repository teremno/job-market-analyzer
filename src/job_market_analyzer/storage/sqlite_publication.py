"""Crash-safe staging and atomic publication for the served SQLite dataset."""

import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

from job_market_analyzer.storage.sqlite import (
    CURRENT_SCHEMA_VERSION,
    connect_read_only_database,
    initialize_database,
)


class DatabasePublicationError(RuntimeError):
    """A database snapshot cannot be safely prepared or published."""


@dataclass(frozen=True, slots=True)
class StagedDatabaseUpdate:
    """Paths involved in one isolated database update."""

    target_path: Path
    staging_path: Path
    previous_path: Path | None


def previous_database_path(database_path: Path) -> Path:
    """Return the single rollback snapshot path for a published database."""

    return database_path.with_name(
        f"{database_path.stem}.previous{database_path.suffix}"
    )


@contextmanager
def staged_database_update(database_path: Path) -> Iterator[StagedDatabaseUpdate]:
    """Yield an isolated copy and publish it only after full validation.

    A sibling path is required so the final ``os.replace`` stays on one filesystem.
    Recoverable source/analyzer failures may still produce a valid published dataset;
    an exception or validation failure leaves the served target unchanged.
    """

    target_path = database_path.resolve(strict=False)
    parent = target_path.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"Database directory does not exist: {parent}")

    lock_path = target_path.with_name(f".{target_path.name}.update.lock")
    lock_fd = _acquire_lock(lock_path)
    staging_path: Path | None = None
    temporary_backup: Path | None = None
    previous_path: Path | None = None
    try:
        staging_path = _temporary_path(target_path, "staging")
        if target_path.exists():
            if not target_path.is_file():
                raise DatabasePublicationError("SQLite database path is not a file")
            previous_path = previous_database_path(target_path)
            temporary_backup = _temporary_path(target_path, "previous")
            _snapshot_database(target_path, temporary_backup)
            validate_database_file(temporary_backup, require_current_schema=False)
            os.replace(temporary_backup, previous_path)
            _sync_directory(parent)
            temporary_backup = None
            shutil.copy2(previous_path, staging_path)

        update = StagedDatabaseUpdate(
            target_path=target_path,
            staging_path=staging_path,
            previous_path=previous_path,
        )
        yield update

        _consolidate_database(staging_path)
        validate_database_file(staging_path, require_current_schema=True)
        os.replace(staging_path, target_path)
        _sync_directory(parent)
    finally:
        for path in (temporary_backup, staging_path):
            if path is not None:
                _remove_if_present(path)
                _remove_sidecars(path)
        os.close(lock_fd)
        _remove_if_present(lock_path)


def validate_database_file(
    database_path: Path,
    *,
    require_current_schema: bool,
) -> None:
    """Reject corrupt SQLite snapshots, FK violations, or stale published schemas."""

    try:
        with closing(connect_read_only_database(database_path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                detail = "unknown" if integrity is None else str(integrity[0])
                raise DatabasePublicationError(
                    f"SQLite integrity check failed: {detail}"
                )
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise DatabasePublicationError(
                    "SQLite foreign key check found violations"
                )
            if require_current_schema:
                version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                if version != CURRENT_SCHEMA_VERSION:
                    raise DatabasePublicationError(
                        "Published SQLite schema must be version "
                        f"{CURRENT_SCHEMA_VERSION}, got {version}"
                    )
                initialize_database(connection)
    except DatabasePublicationError:
        raise
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        raise DatabasePublicationError(
            "SQLite snapshot validation failed"
        ) from exc


def _snapshot_database(source_path: Path, destination_path: Path) -> None:
    """Use SQLite's online backup API so committed WAL data is included."""

    try:
        with (
            closing(connect_read_only_database(source_path)) as source,
            closing(sqlite3.connect(destination_path)) as destination,
        ):
            source.backup(destination)
    except (OSError, sqlite3.Error) as exc:
        raise DatabasePublicationError(
            "Could not create a consistent SQLite rollback snapshot"
        ) from exc


def _consolidate_database(database_path: Path) -> None:
    """Checkpoint staging WAL state into one self-contained database file."""

    try:
        with closing(sqlite3.connect(database_path)) as connection:
            checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is None or int(checkpoint[0]) != 0:
                raise DatabasePublicationError(
                    "Could not checkpoint the staging SQLite database"
                )
            journal_mode = str(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
            )
            if journal_mode.lower() != "delete":
                raise DatabasePublicationError(
                    "Could not consolidate the staging SQLite database"
                )
    except DatabasePublicationError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise DatabasePublicationError(
            "Could not consolidate the staging SQLite database"
        ) from exc


def _temporary_path(target_path: Path, purpose: str) -> Path:
    suffix = target_path.suffix or ".sqlite3"
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{target_path.stem}.{purpose}.",
        suffix=suffix,
        dir=target_path.parent,
    )
    os.close(descriptor)
    return Path(raw_path)


def _acquire_lock(lock_path: Path) -> int:
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise DatabasePublicationError(
            f"Another update may be running; lock exists: {lock_path}"
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
    except Exception:
        os.close(descriptor)
        _remove_if_present(lock_path)
        raise
    return descriptor


def _remove_sidecars(database_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        _remove_if_present(Path(f"{database_path}{suffix}"))


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _sync_directory(directory: Path) -> None:
    """Persist rename metadata on POSIX; Windows has no directory fsync API."""

    if os.name != "posix":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
