import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from job_market_analyzer.intelligence import (
    EvidenceField,
    MatchKind,
    MentionKind,
    SKILL_TAXONOMY_VERSION,
    SkillAnalysisKey,
    SkillEvidence,
    calculate_skill_input_hash,
    extract_skills,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteSkillIntelligenceRepository,
)

CREATED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def intelligence_connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def insert_posting(connection: sqlite3.Connection) -> UUID:
    canonical_job_id = uuid4()
    posting_id = uuid4()
    connection.execute(
        """
        INSERT INTO canonical_jobs (id, created_at, updated_at)
        VALUES (?, ?, ?)
        """,
        (
            str(canonical_job_id),
            "2026-08-18T10:00:00.000000Z",
            "2026-08-18T10:00:00.000000Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO job_postings (
            id,
            canonical_job_id,
            source_provider,
            source_scope,
            external_id,
            title,
            first_seen_at,
            last_seen_at,
            content_hash,
            latest_observation_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(posting_id),
            str(canonical_job_id),
            "remote_ok",
            "global",
            "12345",
            "Python Developer",
            "2026-08-18T10:00:00.000000Z",
            "2026-08-18T10:00:00.000000Z",
            "a" * 64,
            "b" * 64,
        ),
    )
    connection.commit()
    return posting_id


def analysis_key(
    posting_id: UUID,
    *,
    title: str = "Python Developer",
    taxonomy_version: str = SKILL_TAXONOMY_VERSION,
    extractor_version: str = SKILL_TAXONOMY_VERSION,
) -> SkillAnalysisKey:
    return SkillAnalysisKey(
        job_posting_id=posting_id,
        analyzer_kind="skills",
        taxonomy_version=taxonomy_version,
        extractor_version=extractor_version,
        input_hash=calculate_skill_input_hash(
            title,
            "Шукаємо Python інженера для сервісів з Docker.",
            ("Docker", "Python"),
        ),
    )


def skill_evidence(title: str = "Python Developer"):
    return extract_skills(
        title,
        "Шукаємо Python інженера для сервісів з Docker.",
        ("Docker", "Python"),
    )


def named_gcp_evidence(
    skill_name: str,
    *,
    evidence_field: EvidenceField = EvidenceField.TITLE,
) -> SkillEvidence:
    return SkillEvidence(
        skill_code="gcp",
        skill_name=skill_name,
        evidence_field=evidence_field,
        matched_alias="GCP",
        evidence_text="Досвід із GCP та хмарними сервісами",
        rule_id="gcp.gcp",
        match_kind=MatchKind.EXACT_ALIAS,
        mention_kind=MentionKind.MENTIONED,
    )


def test_repository_persists_one_run_and_exact_evidence_round_trip(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)
    key = analysis_key(posting_id)
    evidence = skill_evidence()

    result = repository.persist_skill_analysis(
        key,
        evidence,
        created_at=CREATED_AT,
    )

    assert result.analysis_created is True
    assert result.evidence_created == len(evidence)
    assert repository.find_analysis_run_id(key) == result.analysis_run_id
    assert repository.get_skill_evidence(result.analysis_run_id) == evidence
    run = intelligence_connection.execute(
        """
        SELECT
            job_posting_id,
            analyzer_kind,
            taxonomy_version,
            extractor_version,
            input_hash,
            created_at
        FROM analysis_runs
        """
    ).fetchone()
    assert dict(run) == {
        "job_posting_id": str(posting_id),
        "analyzer_kind": "skills",
        "taxonomy_version": "1",
        "extractor_version": "1",
        "input_hash": key.input_hash,
        "created_at": "2026-08-18T12:00:00.000000Z",
    }
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM skills"
    ).fetchone()[0] == len({item.skill_code for item in evidence})


def test_repository_persists_zero_findings_run(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)

    result = repository.persist_skill_analysis(
        analysis_key(posting_id, title="Office Manager"),
        (),
        created_at=CREATED_AT,
    )

    assert result.analysis_created is True
    assert result.evidence_created == 0
    assert repository.get_skill_evidence(result.analysis_run_id) == ()
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 1
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM job_skills"
    ).fetchone()[0] == 0


def test_same_version_and_input_is_idempotent(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)
    key = analysis_key(posting_id)
    evidence = skill_evidence()

    first = repository.persist_skill_analysis(key, evidence, created_at=CREATED_AT)
    second = repository.persist_skill_analysis(
        key,
        evidence,
        created_at=CREATED_AT + timedelta(days=1),
    )

    assert second.analysis_run_id == first.analysis_run_id
    assert second.analysis_created is False
    assert second.evidence_created == 0
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 1
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM job_skills"
    ).fetchone()[0] == len(evidence)


def test_changed_input_preserves_historical_run_and_creates_new_run(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)
    first_key = analysis_key(posting_id)
    second_key = analysis_key(posting_id, title="Go Developer")

    first = repository.persist_skill_analysis(
        first_key,
        skill_evidence(),
        created_at=CREATED_AT,
    )
    second = repository.persist_skill_analysis(
        second_key,
        skill_evidence("Go Developer"),
        created_at=CREATED_AT + timedelta(days=1),
    )

    assert first.analysis_run_id != second.analysis_run_id
    assert first.analysis_created is second.analysis_created is True
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 2
    assert repository.get_skill_evidence(first.analysis_run_id) == skill_evidence()
    assert repository.get_skill_evidence(second.analysis_run_id) == skill_evidence(
        "Go Developer"
    )


@pytest.mark.parametrize(
    ("taxonomy_version", "extractor_version"),
    [("2", "1"), ("1", "2")],
)
def test_changed_version_allows_new_run(
    intelligence_connection: sqlite3.Connection,
    taxonomy_version: str,
    extractor_version: str,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)

    first = repository.persist_skill_analysis(
        analysis_key(posting_id),
        skill_evidence(),
        created_at=CREATED_AT,
    )
    second = repository.persist_skill_analysis(
        analysis_key(
            posting_id,
            taxonomy_version=taxonomy_version,
            extractor_version=extractor_version,
        ),
        skill_evidence(),
        created_at=CREATED_AT + timedelta(days=1),
    )

    assert first.analysis_run_id != second.analysis_run_id
    assert second.analysis_created is True


def test_historical_skill_names_are_snapshotted_and_global_label_is_stable(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)

    v1 = repository.persist_skill_analysis(
        analysis_key(posting_id, title="GCP v1"),
        (named_gcp_evidence("Google Cloud"),),
        created_at=CREATED_AT,
    )
    v2 = repository.persist_skill_analysis(
        analysis_key(
            posting_id,
            title="GCP v2",
            taxonomy_version="2",
            extractor_version="2",
        ),
        (named_gcp_evidence("Google Cloud Platform"),),
        created_at=CREATED_AT + timedelta(days=1),
    )
    later_v1 = repository.persist_skill_analysis(
        analysis_key(posting_id, title="GCP v1 changed input"),
        (named_gcp_evidence("Google Cloud"),),
        created_at=CREATED_AT + timedelta(days=2),
    )

    assert repository.get_skill_evidence(v1.analysis_run_id) == (
        named_gcp_evidence("Google Cloud"),
    )
    assert repository.get_skill_evidence(v2.analysis_run_id) == (
        named_gcp_evidence("Google Cloud Platform"),
    )
    assert repository.get_skill_evidence(later_v1.analysis_run_id) == (
        named_gcp_evidence("Google Cloud"),
    )
    assert intelligence_connection.execute(
        "SELECT display_name FROM skills WHERE code = 'gcp'"
    ).fetchone()[0] == "Google Cloud"


def test_skill_evidence_round_trip_preserves_fields_and_order(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)
    description_evidence = named_gcp_evidence(
        "Google Cloud",
        evidence_field=EvidenceField.DESCRIPTION,
    )
    title_evidence = named_gcp_evidence("Google Cloud")

    result = repository.persist_skill_analysis(
        analysis_key(posting_id, title="GCP evidence ordering"),
        (description_evidence, title_evidence),
        created_at=CREATED_AT,
    )

    assert repository.get_skill_evidence(result.analysis_run_id) == (
        title_evidence,
        description_evidence,
    )


def test_skill_analysis_key_rejects_non_skill_analyzer_kind() -> None:
    with pytest.raises(ValueError, match="analyzer_kind='skills'"):
        SkillAnalysisKey(
            job_posting_id=uuid4(),
            analyzer_kind="roles",
            taxonomy_version="1",
            extractor_version="1",
            input_hash="a" * 64,
        )


def test_duplicate_evidence_rolls_back_entire_new_run(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)
    one_evidence = skill_evidence()[0]

    with pytest.raises(sqlite3.IntegrityError):
        repository.persist_skill_analysis(
            analysis_key(posting_id),
            (one_evidence, one_evidence),
            created_at=CREATED_AT,
        )

    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 0
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM job_skills"
    ).fetchone()[0] == 0
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM skills"
    ).fetchone()[0] == 0
    assert intelligence_connection.in_transaction is False


def test_analysis_run_requires_existing_job_posting(
    intelligence_connection: sqlite3.Connection,
) -> None:
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)

    with pytest.raises(sqlite3.IntegrityError):
        repository.persist_skill_analysis(
            analysis_key(uuid4()),
            (),
            created_at=CREATED_AT,
        )

    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 0


def test_deleting_posting_cascades_only_derived_rows(
    intelligence_connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(intelligence_connection)
    repository = SQLiteSkillIntelligenceRepository(intelligence_connection)
    result = repository.persist_skill_analysis(
        analysis_key(posting_id),
        skill_evidence(),
        created_at=CREATED_AT,
    )

    intelligence_connection.execute(
        "DELETE FROM job_postings WHERE id = ?",
        (str(posting_id),),
    )
    intelligence_connection.commit()

    assert repository.get_skill_evidence(result.analysis_run_id) == ()
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 0
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM job_skills"
    ).fetchone()[0] == 0
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM canonical_jobs"
    ).fetchone()[0] == 1
    assert intelligence_connection.execute(
        "SELECT COUNT(*) FROM skills"
    ).fetchone()[0] > 0
    assert intelligence_connection.execute("PRAGMA foreign_key_check").fetchall() == []
