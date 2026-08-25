import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from job_market_analyzer.analytics import AnalysisStatus, PostingSearchFilters
from job_market_analyzer.analytics.sqlite_repository import SQLiteAnalyticsRepository
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
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.services.role_analysis import analyze_job_roles
from job_market_analyzer.services.skill_analysis import analyze_job_skills
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

BASE_TIME = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
FROZEN_NOW = BASE_TIME + timedelta(days=14)


def _frozen_repository(connection: sqlite3.Connection) -> SQLiteAnalyticsRepository:
    return SQLiteAnalyticsRepository(
        connection,
        now_provider=lambda: FROZEN_NOW,
    )


@dataclass(frozen=True, slots=True)
class DatasetIds:
    backend_python: UUID
    backend_go: UUID
    product_zero_skill: UUID
    analyzed_zero: UUID
    changed_without_reanalysis: UUID
    old_version_only: UUID


@pytest.fixture
def analytics_connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


@pytest.fixture
def analytics_dataset(analytics_connection: sqlite3.Connection) -> DatasetIds:
    jobs = SQLiteJobRepository(analytics_connection)
    roles = SQLiteRoleIntelligenceRepository(analytics_connection)
    skills = SQLiteSkillIntelligenceRepository(analytics_connection)

    p1 = _persist(
        jobs,
        source="remote_ok",
        external_id="1",
        title="Backend Engineer",
        company="Alpha Labs",
        description="Build Python services with Docker.",
        tags=("Python",),
        published_at=BASE_TIME + timedelta(days=6),
        fetched_at=BASE_TIME + timedelta(days=6),
    )
    p2 = _persist(
        jobs,
        source="remote_ok",
        external_id="2",
        title="Backend Engineer",
        company="Beta Labs",
        description="We need a Go developer using Docker.",
        tags=("Docker",),
        published_at=BASE_TIME + timedelta(days=5),
        fetched_at=BASE_TIME + timedelta(days=5),
    )
    p3 = _persist(
        jobs,
        source="jobicy",
        external_id="3",
        title="Product Manager",
        company="Gamma Products",
        description="Own roadmap outcomes.",
        published_at=BASE_TIME + timedelta(days=4),
        fetched_at=BASE_TIME + timedelta(days=4),
    )
    p4 = _persist(
        jobs,
        source="jobicy",
        external_id="4",
        title="Office Coordinator",
        company="Percent % Company",
        description="Coordinate schedules.",
        published_at=None,
        fetched_at=BASE_TIME + timedelta(days=3),
    )
    stale = _persist(
        jobs,
        source="remote_ok",
        external_id="5",
        title="Backend Engineer",
        company="Delta Growth",
        description="Build Python services.",
        published_at=BASE_TIME + timedelta(days=2),
        fetched_at=BASE_TIME + timedelta(days=2),
    )
    old_version = _persist(
        jobs,
        source="jobicy",
        external_id="6",
        title="Data Engineer",
        company="Epsilon Data",
        description="Develop SQL pipelines.",
        published_at=BASE_TIME + timedelta(days=1),
        fetched_at=BASE_TIME + timedelta(days=1),
    )

    postings = _postings_by_id(jobs)
    for posting_id in (p1, p2, p3, p4, stale):
        analyze_job_roles(postings[posting_id], roles)
        analyze_job_skills(postings[posting_id], skills)

    _persist(
        jobs,
        source="remote_ok",
        external_id="5",
        title="Marketing Manager",
        company="Delta Growth",
        description="Lead brand strategy.",
        published_at=BASE_TIME + timedelta(days=2),
        fetched_at=BASE_TIME + timedelta(days=7),
    )

    old_posting = _postings_by_id(jobs)[old_version]
    roles.persist_role_analysis(
        RoleAnalysisKey(
            job_posting_id=old_version,
            analyzer_kind="roles",
            taxonomy_version="0",
            extractor_version="0",
            input_hash=calculate_role_input_hash(
                old_posting.title,
                old_posting.description_text,
            ),
        ),
        extract_roles(old_posting.title, old_posting.description_text),
        created_at=BASE_TIME + timedelta(days=8),
    )
    skills.persist_skill_analysis(
        SkillAnalysisKey(
            job_posting_id=old_version,
            analyzer_kind="skills",
            taxonomy_version="1",
            extractor_version="1",
            input_hash=calculate_skill_input_hash(
                old_posting.title,
                old_posting.description_text,
                old_posting.source_tags,
            ),
        ),
        extract_skills(
            old_posting.title,
            old_posting.description_text,
            old_posting.source_tags,
        ),
        created_at=BASE_TIME + timedelta(days=8),
    )
    assert ROLE_TAXONOMY_VERSION == "3"
    assert SKILL_TAXONOMY_VERSION == "5"
    return DatasetIds(p1, p2, p3, p4, stale, old_version)


def test_overview_counts_distinct_postings_and_exact_current_runs(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    overview = _frozen_repository(analytics_connection).get_overview()

    assert overview.posting_count == 6
    assert overview.source_count == 2
    assert overview.current_role_classified_posting_count == 3
    assert overview.current_role_unknown_posting_count == 1
    assert overview.current_role_not_analyzed_posting_count == 2
    assert overview.current_skill_classified_posting_count == 2
    assert overview.current_skill_zero_posting_count == 2
    assert overview.current_skill_not_analyzed_posting_count == 2
    assert [(item.source_provider, item.posting_count) for item in overview.postings_by_source] == [
        ("jobicy", 3),
        ("remote_ok", 3),
    ]
    assert [(item.role_code, item.posting_count) for item in overview.top_roles] == [
        ("backend", 2),
        ("product", 1),
    ]
    assert [(item.skill_code, item.posting_count) for item in overview.top_skills] == [
        ("docker", 2),
        ("go", 1),
        ("python", 1),
    ]


def test_empty_current_dataset_has_stable_empty_results(
    analytics_connection: sqlite3.Connection,
) -> None:
    repository = _frozen_repository(analytics_connection)

    overview = repository.get_overview()
    assert overview.posting_count == 0
    assert overview.source_count == 0
    assert overview.postings_by_source == ()
    assert overview.top_roles == ()
    assert overview.top_skills == ()
    assert repository.list_postings().items == ()
    assert repository.list_source_summaries() == ()
    assert repository.get_role_detail("backend").posting_count == 0
    assert repository.get_skill_detail("python").posting_count == 0


def test_historical_and_changed_input_runs_are_not_current(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    repository = _frozen_repository(analytics_connection)

    stale = repository.list_postings(
        PostingSearchFilters(search_text="Delta Growth")
    ).items[0]
    old_version = repository.list_postings(
        PostingSearchFilters(search_text="Epsilon Data")
    ).items[0]

    for item in (stale, old_version):
        assert item.role_analysis_status is AnalysisStatus.NOT_ANALYZED
        assert item.skill_analysis_status is AnalysisStatus.NOT_ANALYZED
        assert item.roles == ()
        assert item.skills == ()
    assert repository.list_postings(
        PostingSearchFilters(role_code="backend", search_text="Delta")
    ).posting_count == 0
    assert repository.list_postings(
        PostingSearchFilters(skill_code="sql", search_text="Epsilon")
    ).posting_count == 0


def test_posting_list_has_stable_pagination_and_bounded_projection(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    repository = _frozen_repository(analytics_connection)

    first = repository.list_postings(limit=2)
    second = repository.list_postings(limit=2, offset=2)
    repeated = repository.list_postings(limit=2)

    assert first.posting_count == 6
    assert [item.job_posting_id for item in first.items] == [
        analytics_dataset.backend_python,
        analytics_dataset.backend_go,
    ]
    assert first.items == repeated.items
    assert set(item.job_posting_id for item in first.items).isdisjoint(
        item.job_posting_id for item in second.items
    )
    assert not hasattr(first.items[0], "description_text")
    assert not hasattr(first.items[0], "payload")


def test_posting_filters_intersect_and_do_not_inflate_evidence(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    repository = _frozen_repository(analytics_connection)

    assert repository.list_postings(
        PostingSearchFilters(source_provider="jobicy")
    ).posting_count == 3
    assert repository.list_postings(
        PostingSearchFilters(role_code="backend")
    ).posting_count == 2
    assert repository.list_postings(
        PostingSearchFilters(skill_code="docker")
    ).posting_count == 2
    combined = repository.list_postings(
        PostingSearchFilters(role_code="backend", skill_code="python")
    )
    assert combined.posting_count == 1
    assert combined.items[0].job_posting_id == analytics_dataset.backend_python


def test_search_is_case_insensitive_literal_and_parameterized(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    repository = _frozen_repository(analytics_connection)

    assert repository.list_postings(
        PostingSearchFilters(search_text="alpha LABS")
    ).posting_count == 1
    assert repository.list_postings(
        PostingSearchFilters(search_text="%")
    ).posting_count == 1
    hostile = repository.list_postings(
        PostingSearchFilters(search_text="%' OR 1=1 --")
    )
    assert hostile.posting_count == 0
    assert analytics_connection.execute(
        "SELECT COUNT(*) FROM job_postings"
    ).fetchone()[0] == 6


def test_role_detail_counts_distinct_postings_and_mentioned_skills(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    detail = _frozen_repository(analytics_connection).get_role_detail(
        "backend"
    )

    assert detail is not None
    assert detail.role_name == "Backend"
    assert detail.posting_count == 2
    assert [(item.skill_code, item.posting_count) for item in detail.top_skills] == [
        ("docker", 2),
        ("go", 1),
        ("python", 1),
    ]
    assert len(detail.representative_postings) == 2
    assert _frozen_repository(analytics_connection).get_role_detail(
        "not-a-role"
    ) is None


def test_skill_detail_counts_roles_and_cooccurrence_once_per_posting(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    detail = _frozen_repository(analytics_connection).get_skill_detail(
        "docker"
    )

    assert detail is not None
    assert detail.skill_name == "Docker"
    assert detail.posting_count == 2
    assert [(item.role_code, item.posting_count) for item in detail.top_roles] == [
        ("backend", 2)
    ]
    assert [
        (item.skill_code, item.posting_count)
        for item in detail.co_occurring_skills
    ] == [("go", 1), ("python", 1)]
    assert all(
        item.skill_code != "docker" for item in detail.co_occurring_skills
    )
    assert _frozen_repository(analytics_connection).get_skill_detail(
        "not-a-skill"
    ) is None


def test_source_summaries_report_freshness_and_three_analysis_states(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    summaries = {
        item.source_provider: item
        for item in _frozen_repository(
            analytics_connection
        ).list_source_summaries()
    }

    assert set(summaries) == {"jobicy", "remote_ok"}
    jobicy = summaries["jobicy"]
    assert jobicy.posting_count == 3
    assert jobicy.current_role_classified_posting_count == 1
    assert jobicy.current_role_unknown_posting_count == 1
    assert jobicy.current_role_not_analyzed_posting_count == 1
    assert jobicy.current_role_classified_percentage == pytest.approx(100 / 3)
    assert jobicy.current_skill_classified_posting_count == 0
    assert jobicy.current_skill_zero_posting_count == 2
    assert jobicy.current_skill_not_analyzed_posting_count == 1
    assert jobicy.current_skill_classified_percentage == 0.0
    assert jobicy.newest_published_at == BASE_TIME + timedelta(days=4)
    assert summaries["remote_ok"].newest_last_seen_at == BASE_TIME + timedelta(days=7)


def test_analyzed_zero_is_distinct_from_not_analyzed_in_list_items(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    repository = _frozen_repository(analytics_connection)
    zero = repository.list_postings(
        PostingSearchFilters(search_text="Office Coordinator")
    ).items[0]
    missing = repository.list_postings(
        PostingSearchFilters(search_text="Data Engineer")
    ).items[0]

    assert zero.role_analysis_status is AnalysisStatus.ANALYZED_ZERO
    assert zero.skill_analysis_status is AnalysisStatus.ANALYZED_ZERO
    assert missing.role_analysis_status is AnalysisStatus.NOT_ANALYZED
    assert missing.skill_analysis_status is AnalysisStatus.NOT_ANALYZED


def test_queries_do_not_mutate_database_bytes_or_total_changes(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    before = hashlib.sha256(analytics_connection.serialize()).digest()
    changes_before = analytics_connection.total_changes
    repository = _frozen_repository(analytics_connection)

    repository.get_overview()
    repository.list_postings(PostingSearchFilters(search_text="engineer"))
    repository.get_role_detail("backend")
    repository.get_skill_detail("docker")
    repository.list_source_summaries()

    assert analytics_connection.total_changes == changes_before
    assert hashlib.sha256(analytics_connection.serialize()).digest() == before
    assert analytics_connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("list_postings", {"limit": 0}),
        ("list_postings", {"limit": 101}),
        ("list_postings", {"limit": 1.5}),
        ("list_postings", {"offset": -1}),
        ("list_postings", {"offset": True}),
        ("get_overview", {"top_limit": 101}),
    ],
)
def test_query_limits_are_bounded(
    analytics_connection: sqlite3.Connection,
    method: str,
    kwargs: dict[str, int | float | bool],
) -> None:
    repository = _frozen_repository(analytics_connection)
    with pytest.raises(ValueError):
        getattr(repository, method)(**kwargs)


def test_stale_postings_are_hidden_from_active_queries(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    jobs = SQLiteJobRepository(analytics_connection)
    _persist(
        jobs,
        source="remote_ok",
        external_id="ancient",
        title="Legacy Perl Engineer",
        company="Old Corp",
        description="Maintain legacy systems.",
        published_at=BASE_TIME - timedelta(days=45),
        fetched_at=BASE_TIME - timedelta(days=40),
    )
    repository = _frozen_repository(analytics_connection)

    active_page = repository.list_postings(
        PostingSearchFilters(search_text="Engineer")
    )
    assert active_page.posting_count == 3
    assert all(item.title != "Legacy Perl Engineer" for item in active_page.items)

    stale_page = repository.list_postings(
        PostingSearchFilters(search_text="Engineer"),
        include_stale=True,
    )
    assert stale_page.posting_count == 4
    assert any(item.title == "Legacy Perl Engineer" for item in stale_page.items)

    overview = repository.get_overview()
    assert overview.posting_count == 6

    summaries = {
        item.source_provider: item for item in repository.list_source_summaries()
    }
    assert summaries["remote_ok"].posting_count == 3


def test_role_and_skill_details_count_only_active_postings(
    analytics_connection: sqlite3.Connection,
    analytics_dataset: DatasetIds,
) -> None:
    jobs = SQLiteJobRepository(analytics_connection)
    roles = SQLiteRoleIntelligenceRepository(analytics_connection)
    skills = SQLiteSkillIntelligenceRepository(analytics_connection)
    ancient_id = _persist(
        jobs,
        source="jobicy",
        external_id="ancient-backend",
        title="Backend Engineer",
        company="Ancient Systems",
        description="Build Python services with Docker.",
        tags=("Python",),
        published_at=BASE_TIME - timedelta(days=45),
        fetched_at=BASE_TIME - timedelta(days=40),
    )
    ancient = _postings_by_id(jobs)[ancient_id]
    analyze_job_roles(ancient, roles)
    analyze_job_skills(ancient, skills)

    repository = _frozen_repository(analytics_connection)

    active_page = repository.list_postings(PostingSearchFilters(role_code="backend"))
    assert active_page.posting_count == 2
    assert all(item.company_name != "Ancient Systems" for item in active_page.items)
    stale_page = repository.list_postings(
        PostingSearchFilters(role_code="backend"),
        include_stale=True,
    )
    assert stale_page.posting_count == 3
    assert any(
        item.company_name == "Ancient Systems" for item in stale_page.items
    )

    role_detail = repository.get_role_detail("backend")
    assert role_detail is not None
    assert role_detail.posting_count == 2
    skill_counts = {
        item.skill_code: item.posting_count for item in role_detail.top_skills
    }
    assert skill_counts["python"] == 1
    assert skill_counts["docker"] == 2

    skill_detail = repository.get_skill_detail("python")
    assert skill_detail is not None
    assert skill_detail.posting_count == 1


def _persist(
    repository: SQLiteJobRepository,
    *,
    source: str,
    external_id: str,
    title: str,
    company: str,
    description: str,
    published_at: datetime | None,
    fetched_at: datetime,
    tags: tuple[str, ...] = (),
) -> UUID:
    source_url = f"https://example.test/{source}/{external_id}"
    result = repository.persist_observation(
        RawJob(
            source_provider=source,
            source_scope="global",
            external_id=external_id,
            source_url=source_url,
            fetched_at=fetched_at,
            payload={"external_id": external_id, "title": title},
        ),
        NormalizedJobPosting(
            source_provider=source,
            source_scope="global",
            external_id=external_id,
            source_url=source_url,
            application_url=f"https://apply.example.test/{external_id}",
            title=title,
            company_name=company,
            description_text=description,
            source_tags=tags,
            location_text="Worldwide",
            published_at=published_at,
        ),
    )
    return result.job_posting_id


def _postings_by_id(repository: SQLiteJobRepository):
    return {posting.id: posting for posting in repository.list_job_postings(limit=100)}
