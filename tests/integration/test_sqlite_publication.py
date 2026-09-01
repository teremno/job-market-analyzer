import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from job_market_analyzer.storage.sqlite import (
    connect_database,
    connect_read_only_database,
    initialize_database,
)
from job_market_analyzer.storage.sqlite_publication import (
    DatabasePublicationError,
    previous_database_path,
    staged_database_update,
)


def _initialize_with_run(database_path: Path, provider: str) -> None:
    with closing(connect_database(database_path)) as connection:
        initialize_database(connection)
        connection.execute(
            """
            INSERT INTO source_update_runs (
                source_provider, display_name, status, message,
                fetched_count, persisted_count, failed_count,
                started_at, finished_at
            ) VALUES (?, ?, 'completed', NULL, 1, 1, 0, ?, ?)
            """,
            (
                provider,
                provider.title(),
                "2026-09-01T00:00:00.000000Z",
                "2026-09-01T00:01:00.000000Z",
            ),
        )
        connection.commit()


def _providers(database_path: Path) -> list[str]:
    with closing(connect_read_only_database(database_path)) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT source_provider FROM source_update_runs ORDER BY id"
            )
        ]


def test_staged_update_publishes_valid_database_and_keeps_previous_snapshot(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_with_run(database_path, "before")

    with staged_database_update(database_path) as update:
        with closing(connect_database(update.staging_path)) as connection:
            connection.execute(
                """
                INSERT INTO source_update_runs (
                    source_provider, display_name, status, message,
                    fetched_count, persisted_count, failed_count,
                    started_at, finished_at
                ) VALUES ('after', 'After', 'completed', NULL, 1, 1, 0, ?, ?)
                """,
                (
                    "2026-09-01T01:00:00.000000Z",
                    "2026-09-01T01:01:00.000000Z",
                ),
            )
            connection.commit()

        assert _providers(database_path) == ["before"]

    assert _providers(database_path) == ["before", "after"]
    rollback_path = previous_database_path(database_path)
    assert _providers(rollback_path) == ["before"]
    with closing(connect_read_only_database(rollback_path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    restore_path = tmp_path / "jobs.restore.sqlite3"
    shutil.copy2(rollback_path, restore_path)
    os.replace(restore_path, database_path)
    assert _providers(database_path) == ["before"]


def test_failed_staging_validation_leaves_published_database_unchanged(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_with_run(database_path, "published")

    with pytest.raises(DatabasePublicationError, match="consolidate"):
        with staged_database_update(database_path) as update:
            update.staging_path.write_bytes(b"not a sqlite database")

    assert _providers(database_path) == ["published"]
    assert not list(tmp_path.glob(".jobs.staging.*"))
    assert not list(tmp_path.glob("*.update.lock"))


def test_existing_update_lock_fails_closed_without_touching_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_with_run(database_path, "published")
    lock_path = tmp_path / ".jobs.sqlite3.update.lock"
    lock_path.write_text("pid=123\n", encoding="ascii")

    with pytest.raises(DatabasePublicationError, match="Another update"):
        with staged_database_update(database_path):
            pytest.fail("locked update must not start")

    assert _providers(database_path) == ["published"]
    assert lock_path.read_text(encoding="ascii") == "pid=123\n"


def test_foreign_key_violation_is_never_published(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_with_run(database_path, "published")

    with pytest.raises(
        DatabasePublicationError,
        match="foreign key check found violations",
    ):
        with staged_database_update(database_path) as update:
            with closing(sqlite3.connect(update.staging_path)) as connection:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    """
                    INSERT INTO job_postings (
                        id, canonical_job_id, source_provider, source_scope,
                        external_id, source_url, title, company_name,
                        application_url, description_text, source_tags_json,
                        location_text, is_remote, remote_scope,
                        employment_type, salary_text, salary_min, salary_max,
                        salary_currency, salary_period, source_updated_at,
                        published_at, first_seen_at, last_seen_at,
                        content_hash, latest_observation_hash
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        'test', 'global', 'broken', NULL, 'Broken', NULL,
                        NULL, NULL, '[]', NULL, 1, NULL,
                        NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                        NULL,
                        '2026-09-01T00:00:00.000000Z',
                        '2026-09-01T00:00:00.000000Z',
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        '1111111111111111111111111111111111111111111111111111111111111111'
                    )
                    """
                )
                connection.commit()

    assert _providers(database_path) == ["published"]


@pytest.mark.skipif(os.name == "nt", reason="Windows locks open SQLite files")
def test_in_flight_reader_finishes_on_old_inode_and_new_reader_sees_publication(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    _initialize_with_run(database_path, "before")

    with closing(connect_read_only_database(database_path)) as in_flight:
        in_flight.execute("BEGIN")
        assert [row[0] for row in in_flight.execute(
            "SELECT source_provider FROM source_update_runs ORDER BY id"
        )] == ["before"]

        with staged_database_update(database_path) as update:
            with closing(connect_database(update.staging_path)) as connection:
                connection.execute(
                    """
                    INSERT INTO source_update_runs (
                        source_provider, display_name, status, message,
                        fetched_count, persisted_count, failed_count,
                        started_at, finished_at
                    ) VALUES ('after', 'After', 'completed', NULL, 1, 1, 0, ?, ?)
                    """,
                    (
                        "2026-09-01T02:00:00.000000Z",
                        "2026-09-01T02:01:00.000000Z",
                    ),
                )
                connection.commit()

        assert [row[0] for row in in_flight.execute(
            "SELECT source_provider FROM source_update_runs ORDER BY id"
        )] == ["before"]
        assert _providers(database_path) == ["before", "after"]
