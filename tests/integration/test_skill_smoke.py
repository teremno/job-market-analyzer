import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    SalaryPeriod,
)
from job_market_analyzer.services.skill_smoke import run_skill_smoke
from job_market_analyzer.storage.serialization import calculate_content_hash
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def connection() -> sqlite3.Connection:
    value = connect_database(":memory:")
    initialize_database(value)
    yield value
    value.close()


def persist_posting(
    connection: sqlite3.Connection,
    external_id: str,
    *,
    title: str,
    description: str | None = None,
    tags: tuple[str, ...] = (),
    fetched_at: datetime = FETCHED_AT,
) -> None:
    normalized = NormalizedJobPosting(
        source_provider="remote_ok",
        source_scope="global",
        external_id=external_id,
        source_url=f"https://example.test/jobs/{external_id}",
        title=title,
        company_name=f"Company {external_id}",
        description_text=description,
        source_tags=tags,
        is_remote=True,
    )
    SQLiteJobRepository(connection).persist_observation(
        RawJob(
            source_provider=normalized.source_provider,
            source_scope=normalized.source_scope,
            external_id=normalized.external_id,
            source_url=normalized.source_url,
            fetched_at=fetched_at,
            payload={
                "title": title,
                "description": description,
                "tags": tags,
                "fetched_at": fetched_at.isoformat(),
            },
        ),
        normalized,
    )


def test_durable_posting_read_is_bounded_and_deterministic(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(connection, "z", title="Z job", tags=("z-tag",))
    persist_posting(connection, "a", title="A job", tags=("a-tag",))
    persist_posting(connection, "m", title="M job", tags=("m-tag",))

    postings = SQLiteJobRepository(connection).list_job_postings(limit=2)

    assert [posting.external_id for posting in postings] == ["a", "m"]
    assert postings[0].title == "A job"
    assert postings[0].source_tags == ("a-tag",)


def test_durable_posting_read_preserves_complete_persisted_domain_state(
    connection: sqlite3.Connection,
) -> None:
    normalized = NormalizedJobPosting(
        source_provider="web3_career",
        source_scope="official_api",
        external_id="complete-posting",
        source_url="https://web3.career/complete-posting",
        application_url="https://apply.example.test/complete-posting",
        title="Complete Backend Engineer",
        company_name="Complete Company",
        description_text="Build Python services.",
        source_tags=("Python", "Backend"),
        location_text="Germany",
        is_remote=True,
        remote_scope=RemoteScope.COUNTRY,
        employment_type=EmploymentType.CONTRACT,
        salary_text="EUR 90000-120000 yearly",
        salary_min=Decimal("90000.50"),
        salary_max=Decimal("120000.75"),
        salary_currency="EUR",
        salary_period=SalaryPeriod.YEARLY,
        published_at=FETCHED_AT - timedelta(days=2),
        source_updated_at=FETCHED_AT - timedelta(hours=1),
    )
    repository = SQLiteJobRepository(connection)
    result = repository.persist_observation(
        RawJob(
            source_provider=normalized.source_provider,
            source_scope=normalized.source_scope,
            external_id=normalized.external_id,
            source_url=normalized.source_url,
            fetched_at=FETCHED_AT,
            payload={"complete": True},
        ),
        normalized,
    )

    posting = repository.list_job_postings(limit=1)[0]

    assert posting.id == result.job_posting_id
    assert posting.canonical_job_id == result.canonical_job_id
    assert posting.first_seen_at == FETCHED_AT
    assert posting.last_seen_at == FETCHED_AT
    assert posting.content_hash == calculate_content_hash(normalized)
    assert posting.model_dump(
        exclude={
            "id",
            "canonical_job_id",
            "first_seen_at",
            "last_seen_at",
            "content_hash",
        }
    ) == normalized.model_dump()


def test_skill_smoke_creates_reuses_and_reports_current_scope(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(
        connection,
        "a",
        title="Python Developer",
        description="Build Python services with Docker.",
        tags=("Python", "backend"),
    )
    persist_posting(
        connection,
        "b",
        title="Python Data Engineer",
        description="Use Python and SQL.",
        tags=("data",),
    )
    persist_posting(
        connection,
        "c",
        title="Customer Support Specialist",
        description="Help customers with account questions.",
        tags=("support",),
    )
    posting_reader = SQLiteJobRepository(connection)
    intelligence_repository = SQLiteSkillIntelligenceRepository(connection)

    first = run_skill_smoke(
        posting_reader,
        intelligence_repository,
        limit=3,
    )
    second = run_skill_smoke(
        posting_reader,
        intelligence_repository,
        limit=3,
    )

    assert first.postings_considered == 3
    assert first.new_analysis_runs == 3
    assert first.existing_analysis_runs_reused == 0
    assert first.evidence_created > 0
    assert first.zero_skill_runs == 1
    assert first.postings_with_skills == 2
    assert [(item.name, item.postings) for item in first.top_skills[:3]] == [
        ("Python", 2),
        ("Docker", 1),
        ("SQL", 1),
    ]
    assert [(item.tag, item.postings) for item in first.unrecognized_source_tags] == [
        ("backend", 1),
        ("data", 1),
        ("support", 1),
    ]
    assert first.evidence_samples

    assert second.new_analysis_runs == 0
    assert second.existing_analysis_runs_reused == 3
    assert second.evidence_created == 0
    assert second.zero_skill_runs == 1
    assert second.top_skills == first.top_skills
    assert second.evidence_samples == first.evidence_samples
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 3


def test_changed_current_input_creates_one_new_run(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(connection, "a", title="Python Developer", tags=("Python",))
    posting_reader = SQLiteJobRepository(connection)
    intelligence_repository = SQLiteSkillIntelligenceRepository(connection)
    first = run_skill_smoke(
        posting_reader,
        intelligence_repository,
        limit=1,
    )

    persist_posting(
        connection,
        "a",
        title="Go Developer",
        description="Build services written in Go.",
        tags=("Go",),
        fetched_at=FETCHED_AT + timedelta(hours=1),
    )
    second = run_skill_smoke(
        posting_reader,
        intelligence_repository,
        limit=1,
    )

    assert first.new_analysis_runs == 1
    assert second.new_analysis_runs == 1
    assert second.existing_analysis_runs_reused == 0
    assert [(item.name, item.postings) for item in second.top_skills] == [
        ("Go", 1)
    ]
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 2


def test_evidence_samples_are_bounded_to_ten(
    connection: sqlite3.Connection,
) -> None:
    for index in range(11):
        persist_posting(
            connection,
            f"job-{index:02}",
            title="Python Developer",
        )

    summary = run_skill_smoke(
        SQLiteJobRepository(connection),
        SQLiteSkillIntelligenceRepository(connection),
        limit=11,
    )

    assert len(summary.evidence_samples) == 10


def test_unexpected_extractor_error_is_not_swallowed(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist_posting(connection, "a", title="Python Developer")

    def fail_extraction(*args: object) -> tuple[()]:
        raise RuntimeError("extractor failed")

    monkeypatch.setattr(
        "job_market_analyzer.services.skill_analysis.extract_skills",
        fail_extraction,
    )

    with pytest.raises(RuntimeError, match="extractor failed"):
        run_skill_smoke(
            SQLiteJobRepository(connection),
            SQLiteSkillIntelligenceRepository(connection),
            limit=1,
        )
