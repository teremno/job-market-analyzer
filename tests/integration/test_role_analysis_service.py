import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

import job_market_analyzer.services.role_analysis as role_service
from job_market_analyzer.intelligence import (
    ROLE_TAXONOMY_VERSION,
    SKILL_TAXONOMY_VERSION,
    RoleAnalysisKey,
    SkillAnalysisKey,
    calculate_role_input_hash,
    calculate_skill_input_hash,
    extract_roles,
    extract_skills,
)
from job_market_analyzer.models import JobPosting, NormalizedJobPosting, RawJob
from job_market_analyzer.services.role_analysis import analyze_job_roles
from job_market_analyzer.services.skill_analysis import analyze_job_skills
from job_market_analyzer.storage.serialization import calculate_content_hash
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FIRST_SEEN = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def normalized(**changes: object) -> NormalizedJobPosting:
    values: dict[str, object] = {
        "source_provider": "remote_ok",
        "source_scope": "global",
        "external_id": "role-1",
        "source_url": "https://example.test/jobs/role-1",
        "title": "Backend Engineer",
        "company_name": "Example",
        "description_text": "Build Python services.",
        "source_tags": ("Python",),
        "location_text": "Europe",
        "is_remote": True,
    }
    values.update(changes)
    return NormalizedJobPosting(**values)


def persist(
    connection: sqlite3.Connection,
    posting: NormalizedJobPosting,
    *,
    fetched_at: datetime = FIRST_SEEN,
) -> JobPosting:
    result = SQLiteJobRepository(connection).persist_observation(
        RawJob(
            source_provider=posting.source_provider,
            source_scope=posting.source_scope,
            external_id=posting.external_id,
            source_url=posting.source_url,
            fetched_at=fetched_at,
            payload={"title": posting.title, "at": fetched_at.isoformat()},
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


@pytest.mark.parametrize(
    ("title", "expected_codes"),
    [
        ("Backend Engineer", ("backend",)),
        ("Product Manager", ("product",)),
        ("Web3 Marketing Manager", ("marketing_growth",)),
        ("Smart Contract Engineer", ("blockchain_protocol",)),
        ("Chief Happiness Officer", ()),
        ("Backend / Platform Engineer", ("backend", "devops_platform")),
    ],
)
def test_service_uses_real_classifier(
    connection: sqlite3.Connection,
    title: str,
    expected_codes: tuple[str, ...],
) -> None:
    posting = persist(connection, normalized(title=title, description_text=None))
    repository = SQLiteRoleIntelligenceRepository(connection)
    result = analyze_job_roles(posting, repository)
    assert tuple(
        item.role_code for item in repository.get_role_evidence(result.analysis_run_id)
    ) == expected_codes


def test_identical_and_unknown_reruns_reuse_run(connection: sqlite3.Connection) -> None:
    repository = SQLiteRoleIntelligenceRepository(connection)
    for title in ("Backend Engineer", "Chief Happiness Officer"):
        posting = persist(
            connection,
            normalized(external_id=title, title=title, description_text=None),
        )
        first = analyze_job_roles(posting, repository)
        second = analyze_job_roles(posting, repository)
        assert first.analysis_created is True
        assert second.analysis_created is False
        assert second.analysis_run_id == first.analysis_run_id


def test_unknown_exact_rerun_skips_extraction(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posting = persist(
        connection,
        normalized(title="Chief Happiness Officer", description_text=None),
    )
    repository = SQLiteRoleIntelligenceRepository(connection)
    first = analyze_job_roles(posting, repository)
    assert first.evidence_created == 0

    def fail_if_called(_title: str, _description: str | None):
        raise AssertionError("extract_roles must not run for an exact persisted run")

    monkeypatch.setattr(role_service, "extract_roles", fail_if_called)
    second = analyze_job_roles(posting, repository)

    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0


def test_unknown_changed_description_creates_role_run_and_preserves_unknown(
    connection: sqlite3.Connection,
) -> None:
    repository = SQLiteRoleIntelligenceRepository(connection)
    first_posting = persist(
        connection,
        normalized(title="Opportunity", description_text=None),
    )
    unknown = analyze_job_roles(first_posting, repository)
    second_posting = persist(
        connection,
        normalized(
            title="Opportunity",
            description_text="We are hiring a Product Manager.",
        ),
        fetched_at=FIRST_SEEN + timedelta(days=1),
    )
    classified = analyze_job_roles(second_posting, repository)

    assert unknown.analysis_run_id != classified.analysis_run_id
    assert repository.get_role_evidence(unknown.analysis_run_id) == ()
    assert tuple(
        item.role_code
        for item in repository.get_role_evidence(classified.analysis_run_id)
    ) == ("product",)
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "Product Manager"},
        {"description_text": "We are hiring a Product Manager."},
    ],
)
def test_changed_role_input_creates_historical_run(
    connection: sqlite3.Connection,
    changes: dict[str, object],
) -> None:
    repository = SQLiteRoleIntelligenceRepository(connection)
    first = analyze_job_roles(persist(connection, normalized()), repository)
    second_posting = persist(
        connection,
        normalized(**changes),
        fetched_at=FIRST_SEEN + timedelta(days=1),
    )
    second = analyze_job_roles(second_posting, repository)
    assert second.analysis_created is True
    assert second.analysis_run_id != first.analysis_run_id


@pytest.mark.parametrize(
    "changes",
    [
        {"company_name": "Renamed"},
        {"location_text": "Worldwide"},
        {"source_tags": ("Go",)},
        {"salary_min": Decimal(100000), "salary_currency": "USD"},
    ],
)
def test_non_role_changes_reuse_run(
    connection: sqlite3.Connection,
    changes: dict[str, object],
) -> None:
    repository = SQLiteRoleIntelligenceRepository(connection)
    first = analyze_job_roles(persist(connection, normalized()), repository)
    updated = normalized(**changes)
    second = analyze_job_roles(
        persist(connection, updated, fetched_at=FIRST_SEEN + timedelta(days=1)),
        repository,
    )
    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id


def test_skill_and_role_analyses_coexist(connection: sqlite3.Connection) -> None:
    posting = persist(connection, normalized())
    skill_repository = SQLiteSkillIntelligenceRepository(connection)
    role_repository = SQLiteRoleIntelligenceRepository(connection)
    skill_result = analyze_job_skills(posting, skill_repository)
    role_result = analyze_job_roles(posting, role_repository)
    original_skill_evidence = skill_repository.get_skill_evidence(
        skill_result.analysis_run_id
    )
    original_role_evidence = role_repository.get_role_evidence(
        role_result.analysis_run_id
    )

    kinds = {
        row[0]
        for row in connection.execute("SELECT analyzer_kind FROM analysis_runs")
    }
    assert kinds == {"skills", "roles"}
    assert skill_result.analysis_run_id != role_result.analysis_run_id
    assert original_skill_evidence == extract_skills(
        posting.title,
        posting.description_text,
        posting.source_tags,
    )
    assert original_role_evidence == extract_roles(
        posting.title, posting.description_text
    )
    assert connection.execute("SELECT COUNT(*) FROM job_skills").fetchone()[0] > 0
    assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] > 0

    role_repository.persist_role_analysis(
        RoleAnalysisKey(
            job_posting_id=posting.id,
            analyzer_kind="roles",
            taxonomy_version=f"{ROLE_TAXONOMY_VERSION}-future",
            extractor_version=f"{ROLE_TAXONOMY_VERSION}-future",
            input_hash=calculate_role_input_hash(
                posting.title, posting.description_text
            ),
        ),
        original_role_evidence,
        created_at=FIRST_SEEN + timedelta(days=1),
    )
    skill_repository.persist_skill_analysis(
        SkillAnalysisKey(
            job_posting_id=posting.id,
            analyzer_kind="skills",
            taxonomy_version=f"{SKILL_TAXONOMY_VERSION}-future",
            extractor_version=f"{SKILL_TAXONOMY_VERSION}-future",
            input_hash=calculate_skill_input_hash(
                posting.title,
                posting.description_text,
                posting.source_tags,
            ),
        ),
        original_skill_evidence,
        created_at=FIRST_SEEN + timedelta(days=1),
    )
    assert skill_repository.get_skill_evidence(
        skill_result.analysis_run_id
    ) == original_skill_evidence
    assert role_repository.get_role_evidence(
        role_result.analysis_run_id
    ) == original_role_evidence
    assert connection.execute(
        "SELECT COUNT(*) FROM analysis_runs WHERE analyzer_kind = 'skills'"
    ).fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM analysis_runs WHERE analyzer_kind = 'roles'"
    ).fetchone()[0] == 2


def test_source_tags_change_affects_skills_but_reuses_role_run(
    connection: sqlite3.Connection,
) -> None:
    first_posting = persist(connection, normalized(source_tags=("Python",)))
    skill_repository = SQLiteSkillIntelligenceRepository(connection)
    role_repository = SQLiteRoleIntelligenceRepository(connection)
    first_skill = analyze_job_skills(first_posting, skill_repository)
    first_role = analyze_job_roles(first_posting, role_repository)

    second_posting = persist(
        connection,
        normalized(source_tags=("Go",)),
        fetched_at=FIRST_SEEN + timedelta(days=1),
    )
    second_skill = analyze_job_skills(second_posting, skill_repository)
    second_role = analyze_job_roles(second_posting, role_repository)

    assert second_skill.analysis_created is True
    assert second_skill.analysis_run_id != first_skill.analysis_run_id
    assert second_role.analysis_created is False
    assert second_role.analysis_run_id == first_role.analysis_run_id


def test_extractor_exception_is_not_swallowed(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posting = persist(connection, normalized())
    repository = SQLiteRoleIntelligenceRepository(connection)

    def fail_extraction(_title: str, _description: str | None):
        raise RuntimeError("extractor failed")

    monkeypatch.setattr(role_service, "extract_roles", fail_extraction)
    with pytest.raises(RuntimeError, match="extractor failed"):
        analyze_job_roles(posting, repository)


def test_repository_exception_is_not_swallowed(connection: sqlite3.Connection) -> None:
    posting = persist(connection, normalized())

    class FailingRepository:
        def find_analysis_run_id(self, _key):
            raise RuntimeError("repository failed")

    with pytest.raises(RuntimeError, match="repository failed"):
        analyze_job_roles(posting, FailingRepository())  # type: ignore[arg-type]


def test_stale_posting_creates_historical_run_without_overwriting_current_state(
    connection: sqlite3.Connection,
) -> None:
    stale = persist(connection, normalized(title="Backend Engineer"))
    persist(
        connection,
        normalized(title="Product Manager"),
        fetched_at=FIRST_SEEN + timedelta(days=1),
    )
    current = SQLiteJobRepository(connection).list_job_postings(limit=1)[0]
    assert current.id == stale.id
    assert current.title == "Product Manager"

    repository = SQLiteRoleIntelligenceRepository(connection)
    result = analyze_job_roles(stale, repository)

    run = connection.execute(
        "SELECT input_hash FROM analysis_runs WHERE id = ?",
        (str(result.analysis_run_id),),
    ).fetchone()
    assert run["input_hash"] == calculate_role_input_hash(
        stale.title, stale.description_text
    )
    assert SQLiteJobRepository(connection).list_job_postings(limit=1)[0].title == (
        "Product Manager"
    )
