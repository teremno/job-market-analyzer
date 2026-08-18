import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from job_market_analyzer.intelligence import extract_skills
from job_market_analyzer.models import JobPosting, NormalizedJobPosting, RawJob
from job_market_analyzer.services.skill_analysis import analyze_job_skills
from job_market_analyzer.storage.serialization import calculate_content_hash
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FIRST_SEEN = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def service_connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def normalized_posting(**changes: object) -> NormalizedJobPosting:
    values: dict[str, object] = {
        "source_provider": "remote_ok",
        "source_scope": "global",
        "external_id": "12345",
        "source_url": "https://remoteok.com/remote-jobs/12345",
        "title": "Python Developer",
        "company_name": "Example Company",
        "description_text": "Build Python services with Docker.",
        "source_tags": ("Docker", "Python"),
        "location_text": "Europe",
        "is_remote": True,
    }
    values.update(changes)
    return NormalizedJobPosting(**values)


def persist_current_posting(
    connection: sqlite3.Connection,
    posting: NormalizedJobPosting,
    *,
    fetched_at: datetime,
    payload_revision: str,
) -> JobPosting:
    result = SQLiteJobRepository(connection).persist_observation(
        RawJob(
            source_provider=posting.source_provider,
            source_scope=posting.source_scope,
            external_id=posting.external_id,
            source_url=posting.source_url,
            fetched_at=fetched_at,
            payload={"revision": payload_revision, "title": posting.title},
        ),
        posting,
    )
    return JobPosting(
        **posting.model_dump(),
        id=result.job_posting_id,
        canonical_job_id=result.canonical_job_id,
        first_seen_at=FIRST_SEEN,
        last_seen_at=fetched_at,
        content_hash=calculate_content_hash(posting),
    )


def test_service_uses_real_extractor_and_is_idempotent(
    service_connection: sqlite3.Connection,
) -> None:
    posting = persist_current_posting(
        service_connection,
        normalized_posting(),
        fetched_at=FIRST_SEEN,
        payload_revision="a",
    )
    repository = SQLiteSkillIntelligenceRepository(service_connection)

    first = analyze_job_skills(posting, repository)
    second = analyze_job_skills(posting, repository)

    assert first.analysis_created is True
    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id
    assert repository.get_skill_evidence(first.analysis_run_id) == extract_skills(
        posting.title,
        posting.description_text,
        posting.source_tags,
    )
    assert service_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 1


def test_changed_skill_input_creates_new_service_run(
    service_connection: sqlite3.Connection,
) -> None:
    first_posting = persist_current_posting(
        service_connection,
        normalized_posting(),
        fetched_at=FIRST_SEEN,
        payload_revision="a",
    )
    repository = SQLiteSkillIntelligenceRepository(service_connection)
    first = analyze_job_skills(first_posting, repository)
    second_posting = persist_current_posting(
        service_connection,
        normalized_posting(
            title="Go Developer",
            description_text="Build services written in Go.",
            source_tags=("Go",),
        ),
        fetched_at=FIRST_SEEN + timedelta(days=1),
        payload_revision="b",
    )

    second = analyze_job_skills(second_posting, repository)

    assert second.analysis_created is True
    assert second.analysis_run_id != first.analysis_run_id
    assert service_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 2


def test_non_skill_posting_change_reuses_existing_service_run(
    service_connection: sqlite3.Connection,
) -> None:
    first_normalized = normalized_posting()
    first_posting = persist_current_posting(
        service_connection,
        first_normalized,
        fetched_at=FIRST_SEEN,
        payload_revision="a",
    )
    repository = SQLiteSkillIntelligenceRepository(service_connection)
    first = analyze_job_skills(first_posting, repository)
    second_normalized = normalized_posting(
        company_name="Renamed Company",
        location_text="Worldwide",
        salary_min=Decimal(90000),
        salary_max=Decimal(120000),
        salary_currency="USD",
    )
    second_posting = persist_current_posting(
        service_connection,
        second_normalized,
        fetched_at=FIRST_SEEN + timedelta(days=1),
        payload_revision="b",
    )

    second = analyze_job_skills(second_posting, repository)

    assert calculate_content_hash(first_normalized) != calculate_content_hash(
        second_normalized
    )
    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id
    assert service_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 1


def test_zero_findings_rerun_does_not_duplicate_analysis(
    service_connection: sqlite3.Connection,
) -> None:
    posting = persist_current_posting(
        service_connection,
        normalized_posting(
            title="Customer Support Specialist",
            description_text="Help customers solve account questions.",
            source_tags=("support",),
        ),
        fetched_at=FIRST_SEEN,
        payload_revision="a",
    )
    repository = SQLiteSkillIntelligenceRepository(service_connection)

    first = analyze_job_skills(posting, repository)
    second = analyze_job_skills(posting, repository)

    assert first.analysis_created is True
    assert first.evidence_created == 0
    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id
    assert service_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 1
    assert service_connection.execute(
        "SELECT COUNT(*) FROM job_skills"
    ).fetchone()[0] == 0
