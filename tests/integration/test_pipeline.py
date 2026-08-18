import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

import pytest

import job_market_analyzer.storage.sqlite as sqlite_storage
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.storage.serialization import (
    calculate_content_hash,
    calculate_observation_hash,
    serialize_raw_payload,
    serialize_utc_datetime,
)
from job_market_analyzer.storage.sqlite import (
    InconsistentDatabaseSchemaError,
    SKILL_INTELLIGENCE_SCHEMA_VERSION,
    UnsupportedDatabaseSchemaVersionError,
    connect_database,
    initialize_database,
    load_intelligence_schema,
    load_schema,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

VALID_HASH_A = "a" * 64
VALID_HASH_B = "b" * 64


def schema_without_source_tags() -> str:
    return (
        load_schema()
        .replace("    source_tags_json TEXT NOT NULL DEFAULT '[]',\n", "")
        .replace("    CHECK (json_valid(source_tags_json)),\n", "")
        .replace("    CHECK (json_type(source_tags_json) = 'array'),\n", "")
    )


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)

    yield connection

    connection.close()


def insert_canonical_job(
    connection: sqlite3.Connection,
    canonical_job_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO canonical_jobs (
            id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?)
        """,
        (
            canonical_job_id,
            "2026-08-17T10:00:00.000000Z",
            "2026-08-17T10:00:00.000000Z",
        ),
    )


def insert_job_posting(
    connection: sqlite3.Connection,
    *,
    posting_id: str,
    canonical_job_id: str,
    source_provider: str = "greenhouse",
    source_scope: str = "example-company",
    external_id: str = "12345",
    salary_currency: str | None = None,
    content_hash: str = VALID_HASH_A,
    latest_observation_hash: str = VALID_HASH_A,
) -> None:
    connection.execute(
        """
        INSERT INTO job_postings (
            id,
            canonical_job_id,
            source_provider,
            source_scope,
            external_id,
            source_url,
            title,
            salary_currency,
            first_seen_at,
            last_seen_at,
            content_hash,
            latest_observation_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            posting_id,
            canonical_job_id,
            source_provider,
            source_scope,
            external_id,
            "https://example.com/jobs/12345",
            "Python Developer",
            salary_currency,
            "2026-08-17T10:00:00.000000Z",
            "2026-08-17T10:00:00.000000Z",
            content_hash,
            latest_observation_hash,
        ),
    )


def insert_raw_job(
    connection: sqlite3.Connection,
    *,
    posting_id: str,
    raw_job: RawJob,
) -> None:
    connection.execute(
        """
        INSERT INTO raw_jobs (
            id,
            job_posting_id,
            source_provider,
            source_scope,
            external_id,
            source_url,
            fetched_at,
            observation_hash,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(raw_job.id),
            posting_id,
            raw_job.source_provider,
            raw_job.source_scope,
            raw_job.external_id,
            str(raw_job.source_url) if raw_job.source_url is not None else None,
            serialize_utc_datetime(raw_job.fetched_at),
            calculate_observation_hash(raw_job),
            serialize_raw_payload(raw_job.payload),
        ),
    )


def test_storage_initializes_required_tables(
    connection: sqlite3.Connection,
) -> None:
    tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    assert {
        "analysis_runs",
        "canonical_jobs",
        "job_skills",
        "job_postings",
        "raw_jobs",
        "skills",
    }.issubset(tables)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_storage_initialization_is_idempotent(
    connection: sqlite3.Connection,
) -> None:
    initialize_database(connection)

    tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    assert {
        "analysis_runs",
        "canonical_jobs",
        "job_skills",
        "job_postings",
        "raw_jobs",
        "skills",
    }.issubset(tables)


def test_storage_rejects_future_schema_without_mutating_database() -> None:
    future_connection = connect_database(":memory:")

    try:
        future_connection.execute("PRAGMA user_version = 3")
        schema_before = future_connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()

        with pytest.raises(
            UnsupportedDatabaseSchemaVersionError,
            match="newer than supported version 2",
        ):
            initialize_database(future_connection)

        assert future_connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert future_connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall() == schema_before
    finally:
        future_connection.close()


def test_storage_rejects_v2_missing_intelligence_tables() -> None:
    malformed_connection = connect_database(":memory:")

    try:
        malformed_connection.executescript(load_schema())
        malformed_connection.execute("PRAGMA user_version = 2")

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="missing tables: analysis_runs, job_skills, skills",
        ):
            initialize_database(malformed_connection)

        assert malformed_connection.execute("PRAGMA user_version").fetchone()[0] == 2
    finally:
        malformed_connection.close()


def test_storage_rejects_v2_missing_critical_intelligence_column() -> None:
    malformed_connection = connect_database(":memory:")
    malformed_schema = (
        load_intelligence_schema()
        .replace("    skill_name TEXT NOT NULL,\n", "")
        .replace("    CHECK (length(trim(skill_name)) > 0),\n", "")
    )

    try:
        malformed_connection.executescript(load_schema())
        malformed_connection.executescript(malformed_schema)
        malformed_connection.execute("PRAGMA user_version = 2")

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="missing columns: skill_name",
        ):
            initialize_database(malformed_connection)

        assert malformed_connection.execute("PRAGMA user_version").fetchone()[0] == 2
    finally:
        malformed_connection.close()


def test_storage_rejects_partial_intelligence_schema_at_v1_without_mutation() -> None:
    partial_connection = connect_database(":memory:")

    try:
        partial_connection.executescript(load_schema())
        partial_connection.execute("PRAGMA user_version = 1")
        partial_connection.execute(
            "CREATE TABLE skills (code TEXT PRIMARY KEY, display_name TEXT NOT NULL)"
        )
        partial_connection.commit()
        schema_before = partial_connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="unexpected partial intelligence tables: skills",
        ):
            initialize_database(partial_connection)

        assert partial_connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert partial_connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall() == schema_before
    finally:
        partial_connection.close()


def test_storage_source_urls_are_nullable(connection: sqlite3.Connection) -> None:
    for table_name in ("job_postings", "raw_jobs"):
        source_url = next(
            row
            for row in connection.execute(f"PRAGMA table_info({table_name})")
            if row[1] == "source_url"
        )
        assert source_url[3] == 0


def test_storage_migrates_required_source_urls_without_losing_rows() -> None:
    legacy_schema = schema_without_source_tags().replace(
        "source_url TEXT,",
        "source_url TEXT NOT NULL,",
    ).replace(
        "CHECK (source_url IS NULL OR length(trim(source_url)) > 0)",
        "CHECK (length(trim(source_url)) > 0)",
    )
    legacy_connection = connect_database(":memory:")

    try:
        legacy_connection.executescript(legacy_schema)
        canonical_job_id = str(uuid4())
        posting_id = str(uuid4())
        source_url = "https://example.com/jobs/legacy"
        insert_canonical_job(legacy_connection, canonical_job_id)
        insert_job_posting(
            legacy_connection,
            posting_id=posting_id,
            canonical_job_id=canonical_job_id,
        )
        legacy_connection.execute(
            """
            INSERT INTO raw_jobs (
                id,
                job_posting_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                fetched_at,
                observation_hash,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                posting_id,
                "greenhouse",
                "example-company",
                "12345",
                source_url,
                "2026-08-17T10:00:00.000000Z",
                VALID_HASH_A,
                '{"title":"Python Developer"}',
            ),
        )
        legacy_connection.commit()

        initialize_database(legacy_connection)

        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM job_postings"
        ).fetchone()[0] == 1
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM raw_jobs"
        ).fetchone()[0] == 1
        assert legacy_connection.execute(
            "SELECT source_url FROM raw_jobs"
        ).fetchone()[0] == source_url
        assert legacy_connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        for table_name in ("job_postings", "raw_jobs"):
            source_url_column = next(
                row
                for row in legacy_connection.execute(
                    f"PRAGMA table_info({table_name})"
                )
                if row[1] == "source_url"
            )
            assert source_url_column[3] == 0
    finally:
        legacy_connection.close()


def test_storage_migrates_source_tags_without_losing_rows() -> None:
    legacy_connection = connect_database(":memory:")

    try:
        legacy_connection.executescript(schema_without_source_tags())
        canonical_job_id = str(uuid4())
        posting_id = str(uuid4())
        insert_canonical_job(legacy_connection, canonical_job_id)
        insert_job_posting(
            legacy_connection,
            posting_id=posting_id,
            canonical_job_id=canonical_job_id,
        )
        legacy_connection.commit()

        initialize_database(legacy_connection)
        initialize_database(legacy_connection)

        row = legacy_connection.execute(
            "SELECT id, source_tags_json, content_hash FROM job_postings"
        ).fetchone()
        source_tags_columns = [
            column
            for column in legacy_connection.execute(
                "PRAGMA table_info(job_postings)"
            )
            if column[1] == "source_tags_json"
        ]
        assert row["id"] == posting_id
        assert row["source_tags_json"] == "[]"
        assert row["content_hash"] == calculate_content_hash(
            NormalizedJobPosting(
                source_provider="greenhouse",
                source_scope="example-company",
                external_id="12345",
                source_url="https://example.com/jobs/12345",
                title="Python Developer",
            )
        )
        assert len(source_tags_columns) == 1
        assert source_tags_columns[0][3] == 1
        assert (
            legacy_connection.execute("PRAGMA user_version").fetchone()[0]
            == SKILL_INTELLIGENCE_SCHEMA_VERSION
        )
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM canonical_jobs"
        ).fetchone()[0] == 1
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM job_postings"
        ).fetchone()[0] == 1
    finally:
        legacy_connection.close()


def test_storage_migrates_committed_v1_schema_to_skill_intelligence() -> None:
    legacy_connection = connect_database(":memory:")

    try:
        legacy_connection.executescript(load_schema())
        legacy_connection.execute("PRAGMA user_version = 1")
        canonical_job_id = str(uuid4())
        posting_id = str(uuid4())
        raw_job = RawJob(
            source_provider="greenhouse",
            source_scope="example-company",
            external_id="12345",
            source_url="https://example.com/jobs/12345",
            fetched_at=datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
            payload={"title": "Python Developer"},
        )
        insert_canonical_job(legacy_connection, canonical_job_id)
        insert_job_posting(
            legacy_connection,
            posting_id=posting_id,
            canonical_job_id=canonical_job_id,
        )
        insert_raw_job(
            legacy_connection,
            posting_id=posting_id,
            raw_job=raw_job,
        )
        legacy_connection.commit()

        initialize_database(legacy_connection)
        initialize_database(legacy_connection)

        tables = {
            row[0]
            for row in legacy_connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"analysis_runs", "job_skills", "skills"}.issubset(tables)
        assert (
            legacy_connection.execute("PRAGMA user_version").fetchone()[0]
            == SKILL_INTELLIGENCE_SCHEMA_VERSION
        )
        assert legacy_connection.execute(
            "SELECT id FROM canonical_jobs"
        ).fetchone()[0] == canonical_job_id
        assert legacy_connection.execute(
            "SELECT id FROM job_postings"
        ).fetchone()[0] == posting_id
        assert legacy_connection.execute(
            "SELECT job_posting_id FROM raw_jobs"
        ).fetchone()[0] == posting_id
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()[0] == 0
        assert legacy_connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert legacy_connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        legacy_connection.close()


def test_skill_intelligence_migration_failure_rolls_back_and_retry_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_connection = connect_database(":memory:")

    try:
        legacy_connection.executescript(load_schema())
        legacy_connection.execute("PRAGMA user_version = 1")
        canonical_job_id = str(uuid4())
        posting_id = str(uuid4())
        insert_canonical_job(legacy_connection, canonical_job_id)
        insert_job_posting(
            legacy_connection,
            posting_id=posting_id,
            canonical_job_id=canonical_job_id,
        )
        insert_raw_job(
            legacy_connection,
            posting_id=posting_id,
            raw_job=RawJob(
                source_provider="greenhouse",
                source_scope="example-company",
                external_id="12345",
                source_url="https://example.com/jobs/12345",
                fetched_at=datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
                payload={"title": "Python Developer"},
            ),
        )
        legacy_connection.commit()
        source_rows_before = {
            "canonical_jobs": [
                dict(row)
                for row in legacy_connection.execute("SELECT * FROM canonical_jobs")
            ],
            "job_postings": [
                dict(row)
                for row in legacy_connection.execute("SELECT * FROM job_postings")
            ],
            "raw_jobs": [
                dict(row) for row in legacy_connection.execute("SELECT * FROM raw_jobs")
            ],
        }

        valid_intelligence_schema = load_intelligence_schema()
        malformed_intelligence_schema = (
            valid_intelligence_schema
            .replace("    skill_name TEXT NOT NULL,\n", "")
            .replace("    CHECK (length(trim(skill_name)) > 0),\n", "")
        )
        monkeypatch.setattr(
            sqlite_storage,
            "load_intelligence_schema",
            lambda: malformed_intelligence_schema,
        )

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="missing columns: skill_name",
        ):
            initialize_database(legacy_connection)

        tables = {
            row[0]
            for row in legacy_connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "skills" not in tables
        assert "job_skills" not in tables
        assert "analysis_runs" not in tables
        assert legacy_connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert legacy_connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert legacy_connection.in_transaction is False
        assert {
            "canonical_jobs": [
                dict(row)
                for row in legacy_connection.execute("SELECT * FROM canonical_jobs")
            ],
            "job_postings": [
                dict(row)
                for row in legacy_connection.execute("SELECT * FROM job_postings")
            ],
            "raw_jobs": [
                dict(row) for row in legacy_connection.execute("SELECT * FROM raw_jobs")
            ],
        } == source_rows_before

        monkeypatch.setattr(
            sqlite_storage,
            "load_intelligence_schema",
            lambda: valid_intelligence_schema,
        )
        initialize_database(legacy_connection)

        assert legacy_connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert {
            "analysis_runs",
            "job_skills",
            "skills",
        }.issubset(
            {
                row[0]
                for row in legacy_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        )
        assert legacy_connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        legacy_connection.close()


def test_source_tags_migration_failure_rolls_back_all_changes() -> None:
    legacy_connection = connect_database(":memory:")

    try:
        legacy_connection.executescript(schema_without_source_tags())
        canonical_job_id = str(uuid4())
        posting_id = str(uuid4())
        raw_job = RawJob(
            source_provider="greenhouse",
            source_scope="example-company",
            external_id="12345",
            source_url="https://example.com/jobs/12345",
            fetched_at=datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
            payload={"title": "Python Developer"},
        )
        observation_hash = calculate_observation_hash(raw_job)
        insert_canonical_job(legacy_connection, canonical_job_id)
        insert_job_posting(
            legacy_connection,
            posting_id=posting_id,
            canonical_job_id=canonical_job_id,
            salary_currency="US",
            latest_observation_hash=observation_hash,
        )
        insert_raw_job(
            legacy_connection,
            posting_id=posting_id,
            raw_job=raw_job,
        )
        legacy_connection.commit()

        canonical_rows_before = [
            dict(row)
            for row in legacy_connection.execute("SELECT * FROM canonical_jobs")
        ]
        posting_rows_before = [
            dict(row)
            for row in legacy_connection.execute("SELECT * FROM job_postings")
        ]
        raw_rows_before = [
            dict(row) for row in legacy_connection.execute("SELECT * FROM raw_jobs")
        ]
        columns_before = [
            tuple(row)
            for row in legacy_connection.execute("PRAGMA table_info(job_postings)")
        ]
        foreign_keys_before = [
            tuple(row)
            for row in legacy_connection.execute("PRAGMA foreign_key_list(raw_jobs)")
        ]
        user_version_before = legacy_connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        with pytest.raises(ValueError, match="salary_currency"):
            initialize_database(legacy_connection)

        columns_after = [
            tuple(row)
            for row in legacy_connection.execute("PRAGMA table_info(job_postings)")
        ]
        foreign_keys_after = [
            tuple(row)
            for row in legacy_connection.execute("PRAGMA foreign_key_list(raw_jobs)")
        ]
        assert user_version_before == 0
        assert legacy_connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert columns_after == columns_before
        assert all(column[1] != "source_tags_json" for column in columns_after)
        assert foreign_keys_after == foreign_keys_before
        assert legacy_connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert [
            dict(row)
            for row in legacy_connection.execute("SELECT * FROM canonical_jobs")
        ] == canonical_rows_before
        assert [
            dict(row)
            for row in legacy_connection.execute("SELECT * FROM job_postings")
        ] == posting_rows_before
        assert [
            dict(row) for row in legacy_connection.execute("SELECT * FROM raw_jobs")
        ] == raw_rows_before
        assert posting_rows_before[0]["id"] == posting_id
        assert posting_rows_before[0]["canonical_job_id"] == canonical_job_id
        assert posting_rows_before[0]["content_hash"] == VALID_HASH_A
        assert raw_rows_before[0]["job_posting_id"] == posting_id
        assert legacy_connection.in_transaction is False
    finally:
        legacy_connection.close()


def test_first_identical_collection_after_source_tags_migration_is_idempotent(
) -> None:
    legacy_connection = connect_database(":memory:")

    try:
        legacy_connection.executescript(schema_without_source_tags())
        canonical_job_id = str(uuid4())
        posting_id = str(uuid4())
        first_raw_job = RawJob(
            source_provider="greenhouse",
            source_scope="example-company",
            external_id="12345",
            source_url="https://example.com/jobs/12345",
            fetched_at=datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
            payload={"title": "Python Developer"},
        )
        observation_hash = calculate_observation_hash(first_raw_job)
        insert_canonical_job(legacy_connection, canonical_job_id)
        insert_job_posting(
            legacy_connection,
            posting_id=posting_id,
            canonical_job_id=canonical_job_id,
            latest_observation_hash=observation_hash,
        )
        insert_raw_job(
            legacy_connection,
            posting_id=posting_id,
            raw_job=first_raw_job,
        )
        legacy_connection.commit()

        initialize_database(legacy_connection)

        migrated_row = legacy_connection.execute(
            """
            SELECT id, canonical_job_id, content_hash, last_seen_at
            FROM job_postings
            """
        ).fetchone()
        migrated_raw_count = legacy_connection.execute(
            "SELECT COUNT(*) FROM raw_jobs"
        ).fetchone()[0]
        repeated_raw_job = first_raw_job.model_copy(
            update={
                "id": uuid4(),
                "fetched_at": datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
            }
        )
        posting = NormalizedJobPosting(
            source_provider="greenhouse",
            source_scope="example-company",
            external_id="12345",
            source_url="https://example.com/jobs/12345",
            title="Python Developer",
        )

        result = SQLiteJobRepository(legacy_connection).persist_observation(
            repeated_raw_job,
            posting,
        )

        current_row = legacy_connection.execute(
            """
            SELECT id, canonical_job_id, content_hash, last_seen_at
            FROM job_postings
            """
        ).fetchone()
        assert str(result.job_posting_id) == migrated_row["id"] == posting_id
        assert (
            str(result.canonical_job_id)
            == migrated_row["canonical_job_id"]
            == canonical_job_id
        )
        assert result.canonical_created is False
        assert result.posting_created is False
        assert result.raw_observation_created is False
        assert result.raw_job_id is None
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM canonical_jobs"
        ).fetchone()[0] == 1
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM job_postings"
        ).fetchone()[0] == 1
        assert legacy_connection.execute(
            "SELECT COUNT(*) FROM raw_jobs"
        ).fetchone()[0] == migrated_raw_count == 1
        assert current_row["content_hash"] == migrated_row["content_hash"]
        assert current_row["content_hash"] == calculate_content_hash(posting)
        assert migrated_row["last_seen_at"] == "2026-08-17T10:00:00.000000Z"
        assert current_row["last_seen_at"] == "2026-08-18T10:00:00.000000Z"
    finally:
        legacy_connection.close()


def test_storage_initialization_rejects_active_transaction(
    connection: sqlite3.Connection,
) -> None:
    connection.execute("BEGIN")

    with pytest.raises(RuntimeError, match="outside an active transaction"):
        initialize_database(connection)

    assert connection.in_transaction
    connection.rollback()


def test_storage_enables_foreign_keys(
    connection: sqlite3.Connection,
) -> None:
    foreign_keys_enabled = connection.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]

    assert foreign_keys_enabled == 1


def test_job_posting_requires_existing_canonical_job(
    connection: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_job_posting(
            connection,
            posting_id=str(uuid4()),
            canonical_job_id=str(uuid4()),
        )


def test_duplicate_source_identity_is_rejected(
    connection: sqlite3.Connection,
) -> None:
    canonical_job_id = str(uuid4())

    insert_canonical_job(
        connection,
        canonical_job_id,
    )

    insert_job_posting(
        connection,
        posting_id=str(uuid4()),
        canonical_job_id=canonical_job_id,
    )

    with pytest.raises(sqlite3.IntegrityError):
        insert_job_posting(
            connection,
            posting_id=str(uuid4()),
            canonical_job_id=canonical_job_id,
        )


def test_same_external_id_in_different_scope_is_allowed(
    connection: sqlite3.Connection,
) -> None:
    canonical_job_id = str(uuid4())

    insert_canonical_job(
        connection,
        canonical_job_id,
    )

    insert_job_posting(
        connection,
        posting_id=str(uuid4()),
        canonical_job_id=canonical_job_id,
        source_scope="company-a",
        external_id="12345",
    )

    insert_job_posting(
        connection,
        posting_id=str(uuid4()),
        canonical_job_id=canonical_job_id,
        source_scope="company-b",
        external_id="12345",
    )

    count = connection.execute(
        "SELECT COUNT(*) FROM job_postings"
    ).fetchone()[0]

    assert count == 2


def test_raw_job_requires_existing_job_posting(
    connection: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO raw_jobs (
                id,
                job_posting_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                fetched_at,
                observation_hash,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                str(uuid4()),
                "greenhouse",
                "example-company",
                "12345",
                "https://example.com/jobs/12345",
                "2026-08-17T10:00:00.000000Z",
                VALID_HASH_B,
                '{"title":"Python Developer"}',
            ),
        )


def test_one_posting_can_have_multiple_raw_observations(
    connection: sqlite3.Connection,
) -> None:
    canonical_job_id = str(uuid4())
    posting_id = str(uuid4())

    insert_canonical_job(
        connection,
        canonical_job_id,
    )

    insert_job_posting(
        connection,
        posting_id=posting_id,
        canonical_job_id=canonical_job_id,
    )

    for observation_hash in (
        VALID_HASH_A,
        VALID_HASH_B,
    ):
        connection.execute(
            """
            INSERT INTO raw_jobs (
                id,
                job_posting_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                fetched_at,
                observation_hash,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                posting_id,
                "greenhouse",
                "example-company",
                "12345",
                "https://example.com/jobs/12345",
                "2026-08-17T10:00:00.000000Z",
                observation_hash,
                '{"title":"Python Developer"}',
            ),
        )

    count = connection.execute(
        """
        SELECT COUNT(*)
        FROM raw_jobs
        WHERE job_posting_id = ?
        """,
        (posting_id,),
    ).fetchone()[0]

    assert count == 2


def test_invalid_json_payload_is_rejected(
    connection: sqlite3.Connection,
) -> None:
    canonical_job_id = str(uuid4())
    posting_id = str(uuid4())

    insert_canonical_job(
        connection,
        canonical_job_id,
    )

    insert_job_posting(
        connection,
        posting_id=posting_id,
        canonical_job_id=canonical_job_id,
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO raw_jobs (
                id,
                job_posting_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                fetched_at,
                observation_hash,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                posting_id,
                "greenhouse",
                "example-company",
                "12345",
                "https://example.com/jobs/12345",
                "2026-08-17T10:00:00.000000Z",
                VALID_HASH_A,
                "not-json",
            ),
        )


def test_invalid_latest_observation_hash_is_rejected(
    connection: sqlite3.Connection,
) -> None:
    canonical_job_id = str(uuid4())

    insert_canonical_job(
        connection,
        canonical_job_id,
    )

    with pytest.raises(sqlite3.IntegrityError):
        insert_job_posting(
            connection,
            posting_id=str(uuid4()),
            canonical_job_id=canonical_job_id,
            latest_observation_hash="invalid",
        )
