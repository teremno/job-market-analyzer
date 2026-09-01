"""Validated timestamped backups for the published SQLite dataset."""

import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from job_market_analyzer.storage.sqlite_publication import (
    DatabasePublicationError,
    create_validated_database_snapshot,
)


class DatabaseBackupError(RuntimeError):
    """A retained SQLite backup could not be created safely."""


@dataclass(frozen=True, slots=True)
class DatabaseBackupResult:
    """Outcome of one validated backup and retention pass."""

    backup_path: Path
    retained_count: int
    removed_count: int


def create_retained_database_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    keep: int,
    created_at: datetime | None = None,
) -> DatabaseBackupResult:
    """Create a validated snapshot and retain the newest matching backups."""

    if keep < 1:
        raise ValueError("Backup retention must be greater than zero")

    source_path = database_path.resolve(strict=False)
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {source_path}")

    destination_directory = backup_directory.resolve(strict=False)
    destination_directory.mkdir(parents=True, exist_ok=True)
    if not destination_directory.is_dir():
        raise NotADirectoryError(
            f"Backup destination is not a directory: {destination_directory}"
        )

    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    backup_path = destination_directory / (
        f"{source_path.stem}.backup-{timestamp:%Y%m%dT%H%M%S.%fZ}"
        f"{source_path.suffix or '.sqlite3'}"
    )
    if backup_path.exists():
        raise DatabaseBackupError(f"Backup path already exists: {backup_path}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{source_path.stem}.backup.",
        suffix=source_path.suffix or ".sqlite3",
        dir=destination_directory,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        create_validated_database_snapshot(
            source_path,
            temporary_path,
            require_current_schema=True,
        )
        os.replace(temporary_path, backup_path)
        _sync_directory(destination_directory)
    except DatabasePublicationError as exc:
        raise DatabaseBackupError("Could not create a validated SQLite backup") from exc
    finally:
        _remove_if_present(temporary_path)
        _remove_sidecars(temporary_path)

    removed_count = _apply_retention(
        destination_directory,
        pattern=_backup_pattern(source_path),
        keep=keep,
    )
    retained_count = len(tuple(destination_directory.glob(_backup_pattern(source_path))))
    return DatabaseBackupResult(
        backup_path=backup_path,
        retained_count=retained_count,
        removed_count=removed_count,
    )


def _backup_pattern(database_path: Path) -> str:
    return f"{database_path.stem}.backup-*{database_path.suffix or '.sqlite3'}"


def _apply_retention(directory: Path, *, pattern: str, keep: int) -> int:
    matching_backups = sorted(directory.glob(pattern), reverse=True)
    expired_backups = matching_backups[keep:]
    try:
        for backup_path in expired_backups:
            backup_path.unlink()
        if expired_backups:
            _sync_directory(directory)
    except OSError as exc:
        raise DatabaseBackupError(
            "Backup was created, but expired backups could not be removed"
        ) from exc
    return len(expired_backups)


def _remove_sidecars(database_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        _remove_if_present(Path(f"{database_path}{suffix}"))


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _sync_directory(directory: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
