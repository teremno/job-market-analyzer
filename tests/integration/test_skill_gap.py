"""Tests for the deterministic read-only skill-gap calculator."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from job_market_analyzer.analytics import SQLiteAnalyticsRepository
from job_market_analyzer.intelligence.hashing import (
    calculate_role_input_hash,
    calculate_skill_input_hash,
)
from job_market_analyzer.intelligence.repository import (
    RoleAnalysisKey,
    SkillAnalysisKey,
)
from job_market_analyzer.intelligence.roles import (
    ROLE_TAXONOMY_VERSION,
    extract_roles,
)
from job_market_analyzer.intelligence.skills import (
    SKILL_TAXONOMY_VERSION,
    extract_skills,
)
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.services.skill_gap import compute_skill_gap
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

BASE_TIME = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
FROZEN_NOW = BASE_TIME + timedelta(days=14)


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def _persist(
    repository: SQLiteJobRepository,
    *,
    source: str,
    external_id: str,
    title: str,
    description: str,
) -> int:
    source_url = f"https://example.test/{source}/{external_id}"
    result = repository.persist_observation(
        RawJob(
            source_provider=source,
            source_scope="global",
            external_id=external_id,
            source_url=source_url,
            fetched_at=BASE_TIME + timedelta(days=1),
            payload={"external_id": external_id},
        ),
        NormalizedJobPosting(
            source_provider=source,
            source_scope="global",
            external_id=external_id,
            source_url=source_url,
            application_url=None,
            title=title,
            company_name="Corp",
            description_text=description,
            source_tags=(),
            location_text=None,
            published_at=BASE_TIME,
        ),
    )
    return result.job_posting_id


def _seed_backend_market(connection: sqlite3.Connection) -> None:
    """Two backend postings mentioning python/docker/k8s; one product posting."""

    jobs = SQLiteJobRepository(connection)
    roles = SQLiteRoleIntelligenceRepository(connection)
    skills = SQLiteSkillIntelligenceRepository(connection)

    _persist(
        jobs,
        source="remote_ok",
        external_id="be-1",
        title="Backend Engineer",
        description="Build Python services with Docker and Kubernetes.",
    )
    _persist(
        jobs,
        source="remote_ok",
        external_id="be-2",
        title="Backend Engineer",
        description="Python, Docker and Kubernetes microservices.",
    )
    _persist(
        jobs,
        source="jobicy",
        external_id="pm-1",
        title="Product Manager",
        description="Own the roadmap and talk to customers.",
    )

    postings = {item.id: item for item in jobs.list_job_postings(limit=100)}
    role_key_by_hash = {}
    skill_key_by_hash = {}
    for posting in postings.values():
        role_key_by_hash[posting.id] = RoleAnalysisKey(
            job_posting_id=posting.id,
            analyzer_kind="roles",
            taxonomy_version=ROLE_TAXONOMY_VERSION,
            extractor_version=ROLE_TAXONOMY_VERSION,
            input_hash=calculate_role_input_hash(
                posting.title, posting.description_text
            ),
        )
        skill_key_by_hash[posting.id] = SkillAnalysisKey(
            job_posting_id=posting.id,
            analyzer_kind="skills",
            taxonomy_version=SKILL_TAXONOMY_VERSION,
            extractor_version=SKILL_TAXONOMY_VERSION,
            input_hash=calculate_skill_input_hash(
                posting.title,
                posting.description_text,
                posting.source_tags,
            ),
        )
        roles.persist_role_analysis(
            role_key_by_hash[posting.id],
            extract_roles(posting.title, posting.description_text),
            created_at=BASE_TIME,
        )
        skills.persist_skill_analysis(
            skill_key_by_hash[posting.id],
            extract_skills(posting.title, posting.description_text, posting.source_tags),
            created_at=BASE_TIME,
        )


def test_gap_orders_by_market_evidence_and_splits_known(
    connection: sqlite3.Connection,
) -> None:
    _seed_backend_market(connection)
    analytics = SQLiteAnalyticsRepository(
        connection, now_provider=lambda: FROZEN_NOW
    )

    report = compute_skill_gap(
        analytics,
        role_code="backend",
        known_skill_inputs=["python", "Docker", "nonexistent-skill"],
    )

    assert report is not None
    assert report.role_code == "backend"
    assert report.role_posting_count == 2
    assert set(report.known_recognized) == {"python", "docker"}
    assert report.unknown_inputs == ("nonexistent-skill",)

    gap_codes = [entry.skill_code for entry in report.gaps]
    assert "kubernetes" in gap_codes
    assert "python" not in gap_codes
    assert "docker" not in gap_codes
    counts = [entry.posting_count for entry in report.gaps]
    assert counts == sorted(counts, reverse=True)
    top = report.gaps[0]
    assert top.share_of_role_postings == pytest.approx(1.0)

    matched = {entry.skill_code for entry in report.matched_market_skills}
    assert {"python", "docker"} <= matched


def test_unknown_role_returns_none(connection: sqlite3.Connection) -> None:
    analytics = SQLiteAnalyticsRepository(
        connection, now_provider=lambda: FROZEN_NOW
    )
    assert (
        compute_skill_gap(analytics, role_code="nope", known_skill_inputs=[])
        is None
    )


def test_blank_inputs_ignored_and_recognition_is_case_insensitive(
    connection: sqlite3.Connection,
) -> None:
    _seed_backend_market(connection)
    analytics = SQLiteAnalyticsRepository(
        connection, now_provider=lambda: FROZEN_NOW
    )

    report = compute_skill_gap(
        analytics,
        role_code="backend",
        known_skill_inputs=["", "   ", "PYTHON"],
    )

    assert report is not None
    assert report.unknown_inputs == ()
    assert "python" in report.known_recognized
