import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from job_market_analyzer.intelligence.roles import extract_roles
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.services.role_smoke import run_role_smoke
from job_market_analyzer.services.skill_analysis import analyze_job_skills
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FETCHED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


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
    company_name: str | None = None,
    fetched_at: datetime = FETCHED_AT,
) -> None:
    normalized = NormalizedJobPosting(
        source_provider="remote_ok",
        source_scope="global",
        external_id=external_id,
        source_url=f"https://example.test/jobs/{external_id}",
        title=title,
        company_name=company_name or f"Company {external_id}",
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
            payload={"observation": external_id},
        ),
        normalized,
    )


def test_role_smoke_creates_reuses_and_reports_current_exact_runs(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(connection, "a", title="Backend Engineer")
    persist_posting(connection, "b", title="Backend / Platform Engineer")
    persist_posting(connection, "c", title="Software Engineer")
    reader = SQLiteJobRepository(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)

    first = run_role_smoke(reader, repository, limit=3)
    second = run_role_smoke(reader, repository, limit=3)

    assert first.postings_considered == 3
    assert first.new_analysis_runs == 3
    assert first.existing_analysis_runs_reused == 0
    assert first.evidence_created == 3
    assert first.classified_postings == 2
    assert first.unknown_postings == 1
    assert first.multi_label_postings == 1
    assert [(item.code, item.postings) for item in first.top_roles] == [
        ("backend", 2),
        ("devops_platform", 1),
    ]
    assert first.unknown_samples[0].job_title == "Software Engineer"
    assert first.multi_label_samples[0].role_codes == (
        "backend",
        "devops_platform",
    )
    assert len(first.evidence_samples) == 3

    assert second.new_analysis_runs == 0
    assert second.existing_analysis_runs_reused == 3
    assert second.evidence_created == 0
    assert second.top_roles == first.top_roles
    assert second.evidence_samples == first.evidence_samples
    assert connection.execute(
        "SELECT COUNT(*) FROM analysis_runs WHERE analyzer_kind = 'roles'"
    ).fetchone()[0] == 3


def test_role_smoke_changed_role_input_creates_new_historical_run(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(connection, "a", title="Software Engineer")
    reader = SQLiteJobRepository(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    first = run_role_smoke(reader, repository, limit=1)

    persist_posting(
        connection,
        "a",
        title="Software Engineer",
        description="We are hiring a Backend Engineer.",
        fetched_at=FETCHED_AT + timedelta(hours=1),
    )
    second = run_role_smoke(reader, repository, limit=1)

    assert first.unknown_postings == 1
    assert second.new_analysis_runs == 1
    assert second.classified_postings == 1
    assert second.top_roles[0].code == "backend"
    assert connection.execute(
        "SELECT COUNT(*) FROM analysis_runs WHERE analyzer_kind = 'roles'"
    ).fetchone()[0] == 2


def test_role_smoke_non_role_change_reuses_run_and_coexists_with_skills(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(
        connection,
        "a",
        title="Backend Engineer",
        tags=("Python",),
        company_name="First Company",
    )
    reader = SQLiteJobRepository(connection)
    roles = SQLiteRoleIntelligenceRepository(connection)
    first = run_role_smoke(reader, roles, limit=1)
    posting = reader.list_job_postings(limit=1)[0]
    analyze_job_skills(posting, SQLiteSkillIntelligenceRepository(connection))

    persist_posting(
        connection,
        "a",
        title="Backend Engineer",
        tags=("Go",),
        company_name="Renamed Company",
        fetched_at=FETCHED_AT + timedelta(hours=1),
    )
    second = run_role_smoke(reader, roles, limit=1)

    assert first.new_analysis_runs == 1
    assert second.new_analysis_runs == 0
    assert second.existing_analysis_runs_reused == 1
    assert {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT analyzer_kind FROM analysis_runs"
        )
    } == {"roles", "skills"}


def test_role_smoke_persisted_evidence_equals_pure_classifier(
    connection: sqlite3.Connection,
) -> None:
    persist_posting(
        connection,
        "a",
        title="Security Engineer - Infrastructure",
        description="Protect production systems.",
    )
    reader = SQLiteJobRepository(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)

    run_role_smoke(reader, repository, limit=1)
    posting = reader.list_job_postings(limit=1)[0]
    run_id = connection.execute(
        "SELECT id FROM analysis_runs WHERE analyzer_kind = 'roles'"
    ).fetchone()[0]

    assert repository.get_role_evidence(UUID(run_id)) == extract_roles(
        posting.title,
        posting.description_text,
    )


def test_role_smoke_samples_are_bounded(
    connection: sqlite3.Connection,
) -> None:
    for index in range(11):
        persist_posting(connection, f"known-{index:02}", title="Backend Engineer")
        persist_posting(connection, f"unknown-{index:02}", title="Software Engineer")
        persist_posting(
            connection,
            f"multi-{index:02}",
            title="Backend / Platform Engineer",
        )

    summary = run_role_smoke(
        SQLiteJobRepository(connection),
        SQLiteRoleIntelligenceRepository(connection),
        limit=33,
    )

    assert len(summary.evidence_samples) == 10
    assert len(summary.unknown_samples) == 10
    assert len(summary.multi_label_samples) == 10


def test_role_smoke_does_not_swallow_extractor_failure(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist_posting(connection, "a", title="Backend Engineer")

    def fail_extraction(*args: object) -> tuple[()]:
        raise RuntimeError("extractor failed")

    monkeypatch.setattr(
        "job_market_analyzer.services.role_analysis.extract_roles",
        fail_extraction,
    )

    with pytest.raises(RuntimeError, match="extractor failed"):
        run_role_smoke(
            SQLiteJobRepository(connection),
            SQLiteRoleIntelligenceRepository(connection),
            limit=1,
        )
