import sqlite3
from uuid import uuid4

import pytest

from job_market_analyzer.storage.sqlite import (
    connect_database,
    initialize_database,
    load_schema,
)

VALID_HASH_A = "a" * 64
VALID_HASH_B = "b" * 64


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
            first_seen_at,
            last_seen_at,
            content_hash,
            latest_observation_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            posting_id,
            canonical_job_id,
            source_provider,
            source_scope,
            external_id,
            "https://example.com/jobs/12345",
            "Python Developer",
            "2026-08-17T10:00:00.000000Z",
            "2026-08-17T10:00:00.000000Z",
            content_hash,
            latest_observation_hash,
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
        "canonical_jobs",
        "job_postings",
        "raw_jobs",
    }.issubset(tables)


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
        "canonical_jobs",
        "job_postings",
        "raw_jobs",
    }.issubset(tables)


def test_storage_source_urls_are_nullable(connection: sqlite3.Connection) -> None:
    for table_name in ("job_postings", "raw_jobs"):
        source_url = next(
            row
            for row in connection.execute(f"PRAGMA table_info({table_name})")
            if row[1] == "source_url"
        )
        assert source_url[3] == 0


def test_storage_migrates_required_source_urls_without_losing_rows() -> None:
    legacy_schema = load_schema().replace(
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
