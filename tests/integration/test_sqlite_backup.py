import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from job_market_analyzer.storage.sqlite import (
    CURRENT_SCHEMA_VERSION,
    connect_database,
    connect_read_only_database,
    initialize_database,
)
from job_market_analyzer.storage.sqlite_backup import (
    DatabaseBackupError,
    create_retained_database_backup,
)


def _initialize_database(database_path: Path) -> None:
    with closing(connect_database(database_path)) as connection:
        initialize_database(connection)
        connection.execute(
            """
            INSERT INTO source_update_runs (
                source_provider, display_name, status, message,
                fetched_count, persisted_count, failed_count,
                started_at, finished_at
            ) VALUES ('test', 'Test', 'completed', NULL, 1, 1, 0, ?, ?)
            """,
            (
                "2026-09-01T00:00:00.000000Z",
                "2026-09-01T00:01:00.000000Z",
            ),
        )
        connection.commit()


def test_backup_is_self_contained_validated_and_retained(tmp_path: Path) -> None:
    database_path = tmp_path / "runtime" / "jobs.sqlite3"
    database_path.parent.mkdir()
    _initialize_database(database_path)
    backup_directory = tmp_path / "backups"
    start = datetime(2026, 9, 1, 5, 0, tzinfo=UTC)

    results = [
        create_retained_database_backup(
            database_path,
            backup_directory,
            keep=2,
            created_at=start + timedelta(days=offset),
        )
        for offset in range(3)
    ]

    retained = sorted(backup_directory.glob("jobs.backup-*.sqlite3"))
    assert retained == [results[1].backup_path, results[2].backup_path]
    assert results[0].backup_path.exists() is False
    assert results[2].retained_count == 2
    assert results[2].removed_count == 1
    assert not list(backup_directory.glob(".*.backup.*"))
    for backup_path in retained:
        with closing(connect_read_only_database(backup_path)) as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("PRAGMA user_version").fetchone()[0] == (
                CURRENT_SCHEMA_VERSION
            )
            assert connection.execute(
                "SELECT COUNT(*) FROM source_update_runs"
            ).fetchone()[0] == 1


def test_failed_backup_leaves_no_partial_snapshot(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")

    backup_directory = tmp_path / "backups"
    with pytest.raises(DatabaseBackupError, match="validated SQLite backup"):
        create_retained_database_backup(
            database_path,
            backup_directory,
            keep=7,
        )

    assert list(backup_directory.iterdir()) == []


def test_backup_retention_does_not_remove_unrelated_files(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_database(database_path)
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    unrelated = backup_directory / "other.backup-20200101T000000.000000Z.sqlite3"
    unrelated.write_bytes(b"unrelated")

    create_retained_database_backup(
        database_path,
        backup_directory,
        keep=1,
        created_at=datetime(2026, 9, 1, 5, 0, tzinfo=UTC),
    )
    create_retained_database_backup(
        database_path,
        backup_directory,
        keep=1,
        created_at=datetime(2026, 9, 2, 5, 0, tzinfo=UTC),
    )

    assert unrelated.read_bytes() == b"unrelated"
    assert len(tuple(backup_directory.glob("jobs.backup-*.sqlite3"))) == 1
