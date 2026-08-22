import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from job_market_analyzer.intelligence.repository import (
    RoleAnalysisKey,
    SeniorityAnalysisKey,
)
from job_market_analyzer.intelligence.seniority import (
    SeniorityEvidence,
    SeniorityEvidenceField,
    SeniorityMatchKind,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
    SQLiteSeniorityIntelligenceRepository,
)

CREATED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _evidence() -> SeniorityEvidence:
    return SeniorityEvidence(
        seniority_code="senior",
        seniority_name="Senior",
        evidence_field=SeniorityEvidenceField.TITLE,
        matched_text="Senior",
        evidence_text="Senior Software Engineer",
        rule_id="senior.named",
        match_kind=SeniorityMatchKind.TITLE_PATTERN,
    )


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def _insert_posting(connection: sqlite3.Connection) -> UUID:
    canonical_id = uuid4()
    posting_id = uuid4()
    now = "2026-08-22T12:00:00.000000Z"
    connection.execute(
        "INSERT INTO canonical_jobs (id, created_at, updated_at) VALUES (?, ?, ?)",
        (str(canonical_id), now, now),
    )
    connection.execute(
        """
        INSERT INTO job_postings (
            id, canonical_job_id, source_provider, source_scope, external_id,
            title, source_tags_json, first_seen_at, last_seen_at,
            content_hash, latest_observation_hash
        )
        VALUES (?, ?, 'test', 'global', '1', 'Senior Software Engineer',
                '[]', ?, ?, ?, ?)
        """,
        (str(posting_id), str(canonical_id), now, now, "a" * 64, "b" * 64),
    )
    connection.commit()
    return posting_id


def test_persist_reuses_identical_run_and_round_trips_evidence(
    connection: sqlite3.Connection,
) -> None:
    posting_id = _insert_posting(connection)
    key = SeniorityAnalysisKey(
        job_posting_id=posting_id,
        analyzer_kind="seniority",
        taxonomy_version="1",
        extractor_version="1",
        input_hash="c" * 64,
    )
    repository = SQLiteSeniorityIntelligenceRepository(connection)

    first = repository.persist_seniority_analysis(
        key, (_evidence(),), created_at=CREATED_AT
    )
    second = repository.persist_seniority_analysis(
        key, (_evidence(),), created_at=CREATED_AT + timedelta(days=1)
    )

    assert first.analysis_created is True
    assert first.evidence_created == 1
    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id
    assert repository.get_seniority_evidence(first.analysis_run_id) == (_evidence(),)


def test_seniority_table_rejects_non_seniority_runs(
    connection: sqlite3.Connection,
) -> None:
    posting_id = _insert_posting(connection)
    role_repository = SQLiteRoleIntelligenceRepository(connection)
    role_key = RoleAnalysisKey(
        job_posting_id=posting_id,
        analyzer_kind="roles",
        taxonomy_version="1",
        extractor_version="1",
        input_hash="d" * 64,
    )
    role_run = role_repository.persist_role_analysis(
        role_key, (), created_at=CREATED_AT
    )

    with pytest.raises(sqlite3.IntegrityError, match="seniority analysis run"):
        connection.execute(
            """
            INSERT INTO job_seniority (
                analysis_run_id, seniority_code, seniority_name,
                evidence_field, matched_text, evidence_text, rule_id, match_kind
            ) VALUES (?, 'senior', 'Senior', 'title', 'Senior',
                      'Senior Software Engineer', 'x', 'title_pattern')
            """,
            # The run above is a roles run; the trigger must abort.
            (str(role_run.analysis_run_id),),
        )


def test_unknown_is_a_zero_evidence_run(connection: sqlite3.Connection) -> None:
    posting_id = _insert_posting(connection)
    key = SeniorityAnalysisKey(
        job_posting_id=posting_id,
        analyzer_kind="seniority",
        taxonomy_version="1",
        extractor_version="1",
        input_hash="e" * 64,
    )
    repository = SQLiteSeniorityIntelligenceRepository(connection)
    result = repository.persist_seniority_analysis(key, (), created_at=CREATED_AT)

    assert result.analysis_created is True
    assert result.evidence_created == 0
    assert repository.get_seniority_evidence(result.analysis_run_id) == ()
