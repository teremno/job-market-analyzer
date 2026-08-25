import sqlite3
from datetime import UTC, datetime

import pytest

from job_market_analyzer.analytics.sqlite_repository import SQLiteAnalyticsRepository
from job_market_analyzer.storage.repository import SourceUpdateRunRecord
from job_market_analyzer.storage.sqlite import (
    InconsistentDatabaseSchemaError,
    SOURCE_UPDATE_RUNS_SCHEMA_VERSION,
    connect_database,
    initialize_database,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

STARTED_AT = datetime(2026, 8, 25, 4, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 8, 25, 4, 5, tzinfo=UTC)
STARTED = "2026-08-25T04:00:00.000000Z"
FINISHED = "2026-08-25T04:05:00.000000Z"


def make_v6_database(connection: sqlite3.Connection) -> None:
    """Build a fully valid current database, then rewind it to version 6."""

    initialize_database(connection)
    connection.execute("DROP INDEX idx_source_update_runs_provider_finished")
    connection.execute("DROP TABLE source_update_runs")
    connection.execute(f"PRAGMA user_version = {SOURCE_UPDATE_RUNS_SCHEMA_VERSION - 1}")
    connection.commit()


def test_valid_v6_migrates_additively_and_preserves_all_prior_data() -> None:
    connection = connect_database(":memory:")
    try:
        make_v6_database(connection)
        before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("canonical_jobs", "job_postings", "raw_jobs", "analysis_runs")
        }

        initialize_database(connection)
        initialize_database(connection)

        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == SOURCE_UPDATE_RUNS_SCHEMA_VERSION
        )
        assert before["canonical_jobs"] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM source_update_runs"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()[0] == before["analysis_runs"]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_partial_update_runs_schema_at_v6_is_rejected_without_mutation() -> None:
    connection = connect_database(":memory:")
    try:
        make_v6_database(connection)
        connection.execute(
            """
            CREATE TABLE source_update_runs (
                id INTEGER PRIMARY KEY, status TEXT
            )
            """
        )
        connection.commit()
        before = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="unexpected partial source update run objects",
        ):
            initialize_database(connection)

        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == SOURCE_UPDATE_RUNS_SCHEMA_VERSION - 1
        )
        assert connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall() == before
        assert connection.in_transaction is False
    finally:
        connection.close()


def test_record_source_update_run_round_trip_and_check_constraints() -> None:
    connection = connect_database(":memory:")
    try:
        initialize_database(connection)
        repository = SQLiteJobRepository(connection)

        repository.record_source_update_run(
            SourceUpdateRunRecord(
                source_provider="remote_ok",
                display_name="Remote OK",
                status="completed",
                started_at=STARTED_AT,
                finished_at=FINISHED_AT,
                fetched_count=10,
                persisted_count=9,
                failed_count=1,
            )
        )

        row = connection.execute(
            """
            SELECT source_provider, display_name, status, message,
                   fetched_count, persisted_count, failed_count,
                   started_at, finished_at
            FROM source_update_runs
            """
        ).fetchone()
        assert row["source_provider"] == "remote_ok"
        assert row["status"] == "completed"
        assert row["message"] is None
        assert tuple(row)[4:7] == (10, 9, 1)
        assert row["started_at"] == STARTED
        assert row["finished_at"] == FINISHED

        with pytest.raises(sqlite3.IntegrityError):
            repository.record_source_update_run(
                SourceUpdateRunRecord(
                    source_provider="remote_ok",
                    display_name="Remote OK",
                    status="completed",
                    started_at=STARTED_AT,
                    finished_at=FINISHED_AT,
                )
            )

        with pytest.raises(sqlite3.IntegrityError):
            repository.record_source_update_run(
                SourceUpdateRunRecord(
                    source_provider="remote_ok",
                    display_name="Remote OK",
                    status="exploded",
                    started_at=STARTED_AT,
                    finished_at=FINISHED_AT,
                )
            )
    finally:
        connection.close()


def test_recorded_history_survives_reinitialization_with_postings_present() -> None:
    connection = connect_database(":memory:")
    try:
        initialize_database(connection)
        repository = SQLiteJobRepository(connection)
        repository.record_source_update_run(
            SourceUpdateRunRecord(
                source_provider="remote_ok",
                display_name="Remote OK",
                status="skipped",
                started_at=STARTED_AT,
                finished_at=STARTED_AT,
                message="TOKEN is not configured",
            )
        )

        initialize_database(connection)

        row = connection.execute(
            "SELECT status, message FROM source_update_runs"
        ).fetchone()
        assert row["status"] == "skipped"
        assert row["message"] == "TOKEN is not configured"
    finally:
        connection.close()


def test_history_only_provider_remains_visible_in_source_summaries() -> None:
    connection = connect_database(":memory:")
    try:
        initialize_database(connection)
        repository = SQLiteJobRepository(connection)
        repository.record_source_update_run(
            SourceUpdateRunRecord(
                source_provider="ghost_source",
                display_name="Ghost Source",
                status="failed",
                started_at=STARTED_AT,
                finished_at=FINISHED_AT,
                message="RuntimeError: temporary source failure",
            )
        )

        summaries = SQLiteAnalyticsRepository(
            connection
        ).list_source_summaries()

        assert len(summaries) == 1
        ghost = summaries[0]
        assert ghost.source_provider == "ghost_source"
        assert ghost.posting_count == 0
        assert ghost.newest_published_at is None
        assert ghost.newest_last_seen_at is None
        assert ghost.current_role_classified_percentage == 0.0
        assert ghost.current_skill_classified_percentage == 0.0
        assert ghost.last_update_status == "failed"
        assert ghost.last_successful_update_at is None
        assert ghost.last_update_finished_at is not None
    finally:
        connection.close()
