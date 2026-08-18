import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    SalaryPeriod,
)
from job_market_analyzer.storage.repository import SourceIdentityMismatchError
from job_market_analyzer.storage.serialization import (
    calculate_content_hash,
    calculate_observation_hash,
    serialize_raw_payload,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FIRST_FETCH = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
SECOND_FETCH = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)

    yield connection

    connection.close()


@pytest.fixture
def repository(connection: sqlite3.Connection) -> SQLiteJobRepository:
    return SQLiteJobRepository(connection)


def test_repository_rejects_connection_without_sqlite_row_factory() -> None:
    plain_connection = sqlite3.connect(":memory:")

    try:
        with pytest.raises(ValueError, match=r"row_factory.*sqlite3\.Row"):
            SQLiteJobRepository(plain_connection)

        assert plain_connection.total_changes == 0
        assert plain_connection.in_transaction is False
    finally:
        plain_connection.close()


def make_raw_job(
    *,
    source_provider: str = "greenhouse",
    source_scope: str = "example-company",
    external_id: str = "12345",
    fetched_at: datetime = FIRST_FETCH,
    payload: dict[str, object] | None = None,
) -> RawJob:
    return RawJob(
        source_provider=source_provider,
        source_scope=source_scope,
        external_id=external_id,
        source_url="https://example.com/jobs/12345",
        fetched_at=fetched_at,
        payload=payload if payload is not None else {"title": "Python Developer"},
    )


def make_posting(
    *,
    source_provider: str = "greenhouse",
    source_scope: str = "example-company",
    external_id: str = "12345",
    title: str = "Python Developer",
    salary_min: Decimal | None = None,
    salary_max: Decimal | None = None,
    published_at: datetime | None = None,
    source_tags: object = (),
) -> NormalizedJobPosting:
    return NormalizedJobPosting(
        source_provider=source_provider,
        source_scope=source_scope,
        external_id=external_id,
        source_url="https://example.com/jobs/12345",
        application_url="https://example.com/apply/12345",
        title=title,
        company_name="Example Company",
        description_text="Build reliable Python services.",
        source_tags=source_tags,
        location_text="Remote - Europe",
        is_remote=True,
        remote_scope=RemoteScope.REGION,
        employment_type=EmploymentType.FULL_TIME,
        salary_text="Published salary",
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="EUR" if salary_min is not None else None,
        salary_period=SalaryPeriod.YEARLY if salary_min is not None else None,
        published_at=published_at,
    )


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    allowed_tables = {"canonical_jobs", "job_postings", "raw_jobs"}
    if table not in allowed_tables:
        raise ValueError(f"Unsupported test table: {table}")

    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_first_observation_creates_complete_persistence_graph(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    raw_job = make_raw_job()

    posting = make_posting()
    result = repository.persist_observation(raw_job, posting)

    assert result.canonical_created is True
    assert result.posting_created is True
    assert result.raw_observation_created is True
    assert result.raw_job_id == raw_job.id
    assert count_rows(connection, "canonical_jobs") == 1
    assert count_rows(connection, "job_postings") == 1
    assert count_rows(connection, "raw_jobs") == 1

    posting_row = connection.execute(
        "SELECT * FROM job_postings WHERE id = ?",
        (str(result.job_posting_id),),
    ).fetchone()
    raw_row = connection.execute(
        "SELECT * FROM raw_jobs WHERE id = ?",
        (str(raw_job.id),),
    ).fetchone()

    assert UUID(posting_row["canonical_job_id"]) == result.canonical_job_id
    assert UUID(raw_row["job_posting_id"]) == result.job_posting_id
    assert posting_row["first_seen_at"] == "2026-08-17T10:00:00.000000Z"
    assert posting_row["last_seen_at"] == "2026-08-17T10:00:00.000000Z"
    assert raw_row["payload_json"] == serialize_raw_payload(raw_job.payload)
    assert raw_row["observation_hash"] == calculate_observation_hash(raw_job)
    assert posting_row["content_hash"] == calculate_content_hash(posting)
    assert posting_row["latest_observation_hash"] == calculate_observation_hash(
        raw_job
    )


def test_unchanged_observation_reuses_ids_and_updates_last_seen(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    first = repository.persist_observation(make_raw_job(), make_posting())
    second_raw = make_raw_job(fetched_at=SECOND_FETCH)

    second = repository.persist_observation(second_raw, make_posting())

    assert second.canonical_job_id == first.canonical_job_id
    assert second.job_posting_id == first.job_posting_id
    assert second.canonical_created is False
    assert second.posting_created is False
    assert second.raw_observation_created is False
    assert second.raw_job_id is None
    assert count_rows(connection, "raw_jobs") == 1

    posting_row = connection.execute(
        "SELECT first_seen_at, last_seen_at FROM job_postings"
    ).fetchone()
    assert posting_row["first_seen_at"] == "2026-08-17T10:00:00.000000Z"
    assert posting_row["last_seen_at"] == "2026-08-18T10:00:00.000000Z"


def test_changed_payload_creates_second_raw_observation(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    repository.persist_observation(make_raw_job(), make_posting())
    changed = make_raw_job(
        fetched_at=SECOND_FETCH,
        payload={"title": "Python Developer", "revision": 2},
    )

    result = repository.persist_observation(changed, make_posting())

    assert result.raw_observation_created is True
    assert result.raw_job_id == changed.id
    assert count_rows(connection, "raw_jobs") == 2


def test_a_to_b_to_a_preserves_all_three_versions(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    payload_a = {"title": "Python Developer", "version": "A"}
    payload_b = {"title": "Python Developer", "version": "B"}

    repository.persist_observation(
        make_raw_job(payload=payload_a),
        make_posting(),
    )
    repository.persist_observation(
        make_raw_job(fetched_at=SECOND_FETCH, payload=payload_b),
        make_posting(),
    )
    third = repository.persist_observation(
        make_raw_job(
            fetched_at=datetime(2026, 8, 19, 10, 0, tzinfo=UTC),
            payload=payload_a,
        ),
        make_posting(),
    )

    assert third.raw_observation_created is True
    assert count_rows(connection, "raw_jobs") == 3


def test_stale_c_arrives_after_b_without_regressing_current_state(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    raw_a = make_raw_job(
        fetched_at=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        payload={"version": "A"},
    )
    raw_b = make_raw_job(
        fetched_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        payload={"version": "B"},
    )
    raw_c = make_raw_job(
        fetched_at=datetime(2026, 8, 18, 11, 0, tzinfo=UTC),
        payload={"version": "C"},
    )
    posting_b = make_posting(title="State B", source_tags=("current",))

    repository.persist_observation(
        raw_a,
        make_posting(title="State A", source_tags=("first",)),
    )
    repository.persist_observation(raw_b, posting_b)
    repository.persist_observation(
        raw_c,
        make_posting(title="State C", source_tags=("stale",)),
    )

    posting_row = connection.execute(
        """
        SELECT title, source_tags_json, last_seen_at, content_hash,
               latest_observation_hash
        FROM job_postings
        """
    ).fetchone()
    raw_hashes = [
        row["observation_hash"]
        for row in connection.execute(
            "SELECT observation_hash FROM raw_jobs ORDER BY rowid"
        )
    ]

    assert posting_row["title"] == "State B"
    assert posting_row["source_tags_json"] == '["current"]'
    assert posting_row["last_seen_at"] == "2026-08-18T12:00:00.000000Z"
    assert posting_row["content_hash"] == calculate_content_hash(posting_b)
    assert posting_row["latest_observation_hash"] == calculate_observation_hash(
        raw_c
    )
    assert raw_hashes == [
        calculate_observation_hash(raw_a),
        calculate_observation_hash(raw_b),
        calculate_observation_hash(raw_c),
    ]


def test_stale_a_rearrival_after_b_uses_arrival_order_hash(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    raw_a_at_10 = make_raw_job(
        fetched_at=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        payload={"version": "A"},
    )
    raw_b = make_raw_job(
        fetched_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        payload={"version": "B"},
    )
    raw_a_at_11 = make_raw_job(
        fetched_at=datetime(2026, 8, 18, 11, 0, tzinfo=UTC),
        payload={"version": "A"},
    )
    posting_b = make_posting(title="State B")

    repository.persist_observation(raw_a_at_10, make_posting(title="State A"))
    repository.persist_observation(raw_b, posting_b)
    repository.persist_observation(raw_a_at_11, make_posting(title="State A"))

    posting_row = connection.execute(
        """
        SELECT title, last_seen_at, content_hash, latest_observation_hash
        FROM job_postings
        """
    ).fetchone()
    raw_hashes = [
        row["observation_hash"]
        for row in connection.execute(
            "SELECT observation_hash FROM raw_jobs ORDER BY rowid"
        )
    ]

    assert posting_row["title"] == "State B"
    assert posting_row["last_seen_at"] == "2026-08-18T12:00:00.000000Z"
    assert posting_row["content_hash"] == calculate_content_hash(posting_b)
    assert posting_row["latest_observation_hash"] == calculate_observation_hash(
        raw_a_at_11
    )
    assert raw_hashes == [
        calculate_observation_hash(raw_a_at_10),
        calculate_observation_hash(raw_b),
        calculate_observation_hash(raw_a_at_11),
    ]


def test_new_normalized_state_updates_posting_and_content_hash(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    first_posting = make_posting(title="Python Developer")
    second_posting = make_posting(title="Senior Python Developer")
    repository.persist_observation(make_raw_job(), first_posting)

    repository.persist_observation(
        make_raw_job(fetched_at=SECOND_FETCH),
        second_posting,
    )

    row = connection.execute(
        "SELECT title, content_hash FROM job_postings"
    ).fetchone()
    assert row["title"] == "Senior Python Developer"
    assert row["content_hash"] == calculate_content_hash(second_posting)
    assert row["content_hash"] != calculate_content_hash(first_posting)


def test_tag_change_updates_same_posting_and_creates_new_raw_observation(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    first_raw = make_raw_job(payload={"title": "Developer", "tags": ["python"]})
    first_posting = make_posting(source_tags=("python",))
    first = repository.persist_observation(first_raw, first_posting)
    second_raw = make_raw_job(
        fetched_at=SECOND_FETCH,
        payload={"title": "Developer", "tags": ["python", "docker"]},
    )
    second_posting = make_posting(source_tags=("python", "docker"))

    second = repository.persist_observation(second_raw, second_posting)

    row = connection.execute(
        "SELECT canonical_job_id, source_tags_json, content_hash FROM job_postings"
    ).fetchone()
    assert second.job_posting_id == first.job_posting_id
    assert second.canonical_job_id == first.canonical_job_id
    assert second.posting_created is False
    assert second.canonical_created is False
    assert second.raw_observation_created is True
    assert count_rows(connection, "canonical_jobs") == 1
    assert count_rows(connection, "job_postings") == 1
    assert count_rows(connection, "raw_jobs") == 2
    assert row["source_tags_json"] == '["docker","python"]'
    assert row["content_hash"] == calculate_content_hash(second_posting)
    assert row["content_hash"] != calculate_content_hash(first_posting)


def test_semantically_unchanged_tag_order_keeps_content_hash(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    first_posting = make_posting(source_tags=["Python", "Docker"])
    repository.persist_observation(
        make_raw_job(payload={"tags": ["Python", "Docker"]}),
        first_posting,
    )
    second_posting = make_posting(source_tags=["Docker", "Python", "Python"])

    repository.persist_observation(
        make_raw_job(
            fetched_at=SECOND_FETCH,
            payload={"tags": ["Docker", "Python", "Python"]},
        ),
        second_posting,
    )

    row = connection.execute(
        "SELECT source_tags_json, content_hash FROM job_postings"
    ).fetchone()
    assert row["source_tags_json"] == '["Docker","Python"]'
    assert row["content_hash"] == calculate_content_hash(first_posting)
    assert row["content_hash"] == calculate_content_hash(second_posting)


def test_stale_changed_observation_preserves_provenance_without_state_regression(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    current_posting = make_posting(title="Current Python Developer")
    current = repository.persist_observation(
        make_raw_job(
            fetched_at=SECOND_FETCH,
            payload={"title": "Current Python Developer"},
        ),
        current_posting,
    )
    stale_raw = make_raw_job(
        fetched_at=FIRST_FETCH,
        payload={"title": "Old Python Developer"},
    )

    stale = repository.persist_observation(
        stale_raw,
        make_posting(title="Old Python Developer"),
    )

    row = connection.execute(
        """
        SELECT canonical_job_id, first_seen_at, last_seen_at, title, content_hash
        FROM job_postings
        """
    ).fetchone()
    assert stale.canonical_job_id == current.canonical_job_id
    assert stale.job_posting_id == current.job_posting_id
    assert stale.raw_observation_created is True
    assert count_rows(connection, "raw_jobs") == 2
    assert row["title"] == "Current Python Developer"
    assert row["content_hash"] == calculate_content_hash(current_posting)
    assert row["first_seen_at"] == "2026-08-18T10:00:00.000000Z"
    assert row["last_seen_at"] == "2026-08-18T10:00:00.000000Z"


@pytest.mark.parametrize(
    ("raw_overrides", "posting_overrides"),
    [
        ({"source_provider": "remote_ok"}, {}),
        ({"source_scope": "other-company"}, {}),
        ({"external_id": "different-id"}, {}),
    ],
)
def test_identity_mismatch_performs_zero_writes(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
    raw_overrides: dict[str, str],
    posting_overrides: dict[str, str],
) -> None:
    with pytest.raises(SourceIdentityMismatchError, match="do not match"):
        repository.persist_observation(
            make_raw_job(**raw_overrides),
            make_posting(**posting_overrides),
        )

    assert count_rows(connection, "canonical_jobs") == 0
    assert count_rows(connection, "job_postings") == 0
    assert count_rows(connection, "raw_jobs") == 0


def test_non_json_payload_fails_before_database_writes(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    raw_job = make_raw_job(payload={"unsupported": object()})

    with pytest.raises(TypeError):
        repository.persist_observation(raw_job, make_posting())

    assert count_rows(connection, "canonical_jobs") == 0
    assert count_rows(connection, "job_postings") == 0
    assert count_rows(connection, "raw_jobs") == 0


def test_raw_insert_failure_rolls_back_new_canonical_and_posting(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    connection.execute(
        """
        CREATE TRIGGER fail_raw_insert
        BEFORE INSERT ON raw_jobs
        BEGIN
            SELECT RAISE(ABORT, 'forced raw insert failure');
        END
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="forced raw insert failure"):
        repository.persist_observation(make_raw_job(), make_posting())

    assert count_rows(connection, "canonical_jobs") == 0
    assert count_rows(connection, "job_postings") == 0
    assert count_rows(connection, "raw_jobs") == 0


def test_existing_posting_failure_rolls_back_and_connection_recovers(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    raw_a = make_raw_job(payload={"version": "A"})
    posting_a = make_posting(title="State A")
    repository.persist_observation(raw_a, posting_a)

    durable_a = dict(connection.execute("SELECT * FROM job_postings").fetchone())
    raw_count_a = count_rows(connection, "raw_jobs")
    raw_b = make_raw_job(
        fetched_at=SECOND_FETCH,
        payload={"version": "B"},
    )
    posting_b = make_posting(title="State B")

    connection.execute(
        """
        CREATE TRIGGER fail_existing_posting_update
        BEFORE UPDATE ON job_postings
        BEGIN
            SELECT RAISE(ABORT, 'forced existing posting update failure');
        END
        """
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="forced existing posting update failure",
    ):
        repository.persist_observation(raw_b, posting_b)

    durable_after_failure = dict(
        connection.execute("SELECT * FROM job_postings").fetchone()
    )
    failed_raw_count = connection.execute(
        "SELECT COUNT(*) FROM raw_jobs WHERE id = ?",
        (str(raw_b.id),),
    ).fetchone()[0]

    assert durable_after_failure == durable_a
    assert durable_after_failure["title"] == "State A"
    assert durable_after_failure["content_hash"] == calculate_content_hash(
        posting_a
    )
    assert durable_after_failure["latest_observation_hash"] == (
        calculate_observation_hash(raw_a)
    )
    assert durable_after_failure["first_seen_at"] == (
        "2026-08-17T10:00:00.000000Z"
    )
    assert durable_after_failure["last_seen_at"] == (
        "2026-08-17T10:00:00.000000Z"
    )
    assert count_rows(connection, "raw_jobs") == raw_count_a
    assert failed_raw_count == 0
    assert connection.in_transaction is False

    connection.execute("DROP TRIGGER fail_existing_posting_update")

    recovered = repository.persist_observation(raw_b, posting_b)

    recovered_row = connection.execute(
        """
        SELECT title, last_seen_at, content_hash, latest_observation_hash
        FROM job_postings
        """
    ).fetchone()
    assert recovered.raw_observation_created is True
    assert recovered.raw_job_id == raw_b.id
    assert recovered_row["title"] == "State B"
    assert recovered_row["last_seen_at"] == "2026-08-18T10:00:00.000000Z"
    assert recovered_row["content_hash"] == calculate_content_hash(posting_b)
    assert recovered_row["latest_observation_hash"] == calculate_observation_hash(
        raw_b
    )
    assert count_rows(connection, "raw_jobs") == raw_count_a + 1
    assert connection.in_transaction is False


@pytest.mark.parametrize(
    ("provider", "scope"),
    [
        ("greenhouse", "other-company"),
        ("remote_ok", "example-company"),
    ],
)
def test_identity_namespace_creates_distinct_postings(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
    provider: str,
    scope: str,
) -> None:
    first = repository.persist_observation(make_raw_job(), make_posting())
    second = repository.persist_observation(
        make_raw_job(source_provider=provider, source_scope=scope),
        make_posting(source_provider=provider, source_scope=scope),
    )

    assert second.job_posting_id != first.job_posting_id
    assert second.canonical_job_id != first.canonical_job_id
    assert count_rows(connection, "canonical_jobs") == 2
    assert count_rows(connection, "job_postings") == 2


def test_decimal_values_round_trip_as_exact_canonical_text(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    posting = make_posting(
        salary_min=Decimal("12345678901234567890.1200"),
        salary_max=Decimal("12345678901234567891.3400"),
    )

    repository.persist_observation(make_raw_job(), posting)

    row = connection.execute(
        "SELECT salary_min, salary_max FROM job_postings"
    ).fetchone()
    assert row["salary_min"] == "12345678901234567890.12"
    assert row["salary_max"] == "12345678901234567891.34"


def test_repository_stores_canonical_utc_timestamps(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    berlin_time = datetime(
        2026,
        8,
        17,
        12,
        30,
        45,
        123456,
        tzinfo=timezone(timedelta(hours=2)),
    )
    repository.persist_observation(
        make_raw_job(fetched_at=berlin_time),
        make_posting(published_at=berlin_time),
    )

    canonical_row = connection.execute(
        "SELECT created_at, updated_at FROM canonical_jobs"
    ).fetchone()
    posting_row = connection.execute(
        "SELECT first_seen_at, last_seen_at, published_at FROM job_postings"
    ).fetchone()
    raw_row = connection.execute("SELECT fetched_at FROM raw_jobs").fetchone()
    expected = "2026-08-17T10:30:45.123456Z"

    assert tuple(canonical_row) == (expected, expected)
    assert tuple(posting_row) == (expected, expected, expected)
    assert raw_row["fetched_at"] == expected


def test_repository_rejects_caller_owned_active_transaction(
    connection: sqlite3.Connection,
    repository: SQLiteJobRepository,
) -> None:
    connection.execute("BEGIN")

    with pytest.raises(RuntimeError, match="without an active transaction"):
        repository.persist_observation(make_raw_job(), make_posting())

    assert connection.in_transaction
    connection.rollback()
