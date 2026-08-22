import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from job_market_analyzer.intelligence import (
    ROLE_TAXONOMY_VERSION,
    RoleAnalysisKey,
    RoleEvidence,
    RoleEvidenceField,
    RoleMatchKind,
    calculate_role_input_hash,
    extract_roles,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
)

CREATED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def insert_posting(connection: sqlite3.Connection) -> UUID:
    canonical_id, posting_id = uuid4(), uuid4()
    now = "2026-08-21T10:00:00.000000Z"
    connection.execute(
        "INSERT INTO canonical_jobs (id, created_at, updated_at) VALUES (?, ?, ?)",
        (str(canonical_id), now, now),
    )
    connection.execute(
        """
        INSERT INTO job_postings (
            id, canonical_job_id, source_provider, source_scope, external_id,
            title, first_seen_at, last_seen_at, content_hash,
            latest_observation_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(posting_id), str(canonical_id), "remote_ok", "global", "1",
            "Backend Engineer", now, now, "a" * 64, "b" * 64,
        ),
    )
    connection.commit()
    return posting_id


def key(
    posting_id: UUID,
    *,
    title: str = "Backend Engineer",
    description: str | None = "Build APIs.",
    taxonomy_version: str = ROLE_TAXONOMY_VERSION,
    extractor_version: str = ROLE_TAXONOMY_VERSION,
) -> RoleAnalysisKey:
    return RoleAnalysisKey(
        job_posting_id=posting_id,
        analyzer_kind="roles",
        taxonomy_version=taxonomy_version,
        extractor_version=extractor_version,
        input_hash=calculate_role_input_hash(title, description),
    )


def named_backend(name: str = "Backend") -> RoleEvidence:
    return RoleEvidence(
        role_code="backend",
        role_name=name,
        evidence_field=RoleEvidenceField.TITLE,
        matched_text="Backend Engineer",
        evidence_text="Backend Engineer",
        rule_id="backend.engineer",
        match_kind=RoleMatchKind.TITLE_PATTERN,
    )


def role_evidence(
    role_code: str,
    role_name: str,
    *,
    matched_text: str,
) -> RoleEvidence:
    return RoleEvidence(
        role_code=role_code,
        role_name=role_name,
        evidence_field=RoleEvidenceField.TITLE,
        matched_text=matched_text,
        evidence_text="Backend Engineer & Product Manager — міжнародна команда",
        rule_id=f"{role_code or 'invalid'}.test",
        match_kind=RoleMatchKind.TITLE_PATTERN,
    )


def test_one_role_round_trips_exactly(connection: sqlite3.Connection) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    evidence = extract_roles("Backend Engineer", "Build APIs.")

    result = repository.persist_role_analysis(
        key(posting_id), evidence, created_at=CREATED_AT
    )

    assert result.analysis_created is True
    assert result.evidence_created == 1
    assert repository.find_analysis_run_id(key(posting_id)) == result.analysis_run_id
    assert repository.get_role_evidence(result.analysis_run_id) == evidence


def test_multi_label_round_trip_is_deterministically_ordered(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    evidence = extract_roles("Backend / Platform Engineer", None)
    assert len(evidence) == 2

    result = repository.persist_role_analysis(
        key(posting_id, title="Backend / Platform Engineer", description=None),
        tuple(reversed(evidence)),
        created_at=CREATED_AT,
    )

    assert repository.get_role_evidence(result.analysis_run_id) == evidence


def test_zero_result_and_identical_rerun_are_persisted_once(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    unknown_key = key(posting_id, title="Chief Happiness Officer", description=None)

    first = repository.persist_role_analysis(unknown_key, (), created_at=CREATED_AT)
    second = repository.persist_role_analysis(
        unknown_key, (), created_at=CREATED_AT + timedelta(days=1)
    )

    assert first.analysis_created is True
    assert second.analysis_created is False
    assert second.analysis_run_id == first.analysis_run_id
    assert repository.get_role_evidence(first.analysis_run_id) == ()
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1


def test_two_identical_writers_converge_on_one_run(tmp_path: Path) -> None:
    database_path = tmp_path / "role-race.sqlite3"
    setup_connection = connect_database(database_path)
    initialize_database(setup_connection)
    posting_id = insert_posting(setup_connection)
    setup_connection.close()
    start = Barrier(2)

    def persist_once():
        connection = connect_database(database_path)
        try:
            repository = SQLiteRoleIntelligenceRepository(connection)
            start.wait()
            return repository.persist_role_analysis(
                key(posting_id),
                (named_backend(),),
                created_at=CREATED_AT,
            )
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _index: persist_once(), range(2)))

    assert sorted(result.analysis_created for result in results) == [False, True]
    assert len({result.analysis_run_id for result in results}) == 1
    verification = connect_database(database_path)
    try:
        assert verification.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()[0] == 1
        assert verification.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 1
    finally:
        verification.close()


@pytest.mark.parametrize(
    ("title", "taxonomy_version", "extractor_version"),
    [
        ("Product Manager", "1", "1"),
        ("Backend Engineer", "2", "1"),
        ("Backend Engineer", "1", "2"),
    ],
)
def test_changed_input_or_version_creates_historical_run(
    connection: sqlite3.Connection,
    title: str,
    taxonomy_version: str,
    extractor_version: str,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    first = repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )
    second_key = key(
        posting_id,
        title=title,
        taxonomy_version=taxonomy_version,
        extractor_version=extractor_version,
    )
    second = repository.persist_role_analysis(
        second_key,
        extract_roles(title, "Build APIs."),
        created_at=CREATED_AT + timedelta(days=1),
    )
    assert second.analysis_created is True
    assert second.analysis_run_id != first.analysis_run_id
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 2


def test_duplicate_role_rolls_back_run_and_reference(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    evidence = named_backend()

    with pytest.raises(sqlite3.IntegrityError):
        repository.persist_role_analysis(
            key(posting_id), (evidence, evidence), created_at=CREATED_AT
        )

    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0
    assert connection.in_transaction is False


@pytest.mark.parametrize(
    "evidence",
    [
        (role_evidence("", "Invalid", matched_text="Invalid"),),
        (role_evidence("backend", "Backend", matched_text=""),),
        (
            named_backend(),
            role_evidence("product", "Product", matched_text=""),
        ),
    ],
)
def test_failure_at_each_evidence_stage_rolls_back_and_connection_recovers(
    connection: sqlite3.Connection,
    evidence: tuple[RoleEvidence, ...],
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    connection.execute("INSERT INTO roles VALUES ('existing', 'Existing')")
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError):
        repository.persist_role_analysis(
            key(posting_id), evidence, created_at=CREATED_AT
        )

    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert [
        tuple(row)
        for row in connection.execute(
            "SELECT code, display_name FROM roles ORDER BY code"
        )
    ] == [("existing", "Existing")]
    assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0
    assert connection.in_transaction is False

    recovery = repository.persist_role_analysis(
        key(posting_id, title="Unknown", description=None),
        (),
        created_at=CREATED_AT + timedelta(seconds=1),
    )
    assert recovery.analysis_created is True


def test_missing_posting_fk_rolls_back(connection: sqlite3.Connection) -> None:
    repository = SQLiteRoleIntelligenceRepository(connection)
    with pytest.raises(sqlite3.IntegrityError):
        repository.persist_role_analysis(key(uuid4()), (), created_at=CREATED_AT)
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def test_active_caller_transaction_is_rejected_without_being_committed(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    connection.execute("INSERT INTO roles VALUES ('caller-owned', 'Caller Owned')")
    assert connection.in_transaction is True

    with pytest.raises(RuntimeError, match="without an active transaction"):
        repository.persist_role_analysis(
            key(posting_id), (named_backend(),), created_at=CREATED_AT
        )

    assert connection.in_transaction is True
    assert connection.execute(
        "SELECT COUNT(*) FROM roles WHERE code = 'caller-owned'"
    ).fetchone()[0] == 1
    connection.rollback()
    assert connection.execute(
        "SELECT COUNT(*) FROM roles WHERE code = 'caller-owned'"
    ).fetchone()[0] == 0

    result = repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )
    assert result.analysis_created is True


def test_role_key_rejects_other_analyzer_kinds() -> None:
    with pytest.raises(ValueError, match="analyzer_kind='roles'"):
        RoleAnalysisKey(
            job_posting_id=uuid4(),
            analyzer_kind="skills",
            taxonomy_version="1",
            extractor_version="1",
            input_hash="a" * 64,
        )


def test_role_repository_rejects_connection_without_row_factory() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        with pytest.raises(ValueError, match="row_factory"):
            SQLiteRoleIntelligenceRepository(connection)
    finally:
        connection.close()


def test_database_prevents_cross_kind_evidence(connection: sqlite3.Connection) -> None:
    posting_id = insert_posting(connection)
    run_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO analysis_runs (
            id, job_posting_id, analyzer_kind, taxonomy_version,
            extractor_version, input_hash, created_at
        ) VALUES (?, ?, 'skills', '1', '1', ?, ?)
        """,
        (run_id, str(posting_id), "c" * 64, "2026-08-21T12:00:00.000000Z"),
    )
    connection.execute("INSERT INTO roles VALUES ('backend', 'Backend')")
    with pytest.raises(sqlite3.IntegrityError, match="roles analysis run"):
        connection.execute(
            """
            INSERT INTO job_roles VALUES (?, 'backend', 'Backend', 'title',
                'Backend Engineer', 'Backend Engineer', 'backend.engineer',
                'title_pattern')
            """,
            (run_id,),
        )
    connection.rollback()


def test_database_prevents_skill_evidence_on_role_run(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    run_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO analysis_runs (
            id, job_posting_id, analyzer_kind, taxonomy_version,
            extractor_version, input_hash, created_at
        ) VALUES (?, ?, 'roles', '1', '1', ?, ?)
        """,
        (run_id, str(posting_id), "d" * 64, "2026-08-21T12:00:00.000000Z"),
    )
    connection.execute("INSERT INTO skills VALUES ('python', 'Python')")
    with pytest.raises(sqlite3.IntegrityError, match="skills analysis run"):
        connection.execute(
            """
            INSERT INTO job_skills VALUES (
                ?, 'python', 'Python', 'title', 'Python', 'Python Developer',
                'python.python', 'exact_alias', 'mentioned'
            )
            """,
            (run_id,),
        )
    connection.rollback()


def test_role_run_kind_cannot_change_after_evidence(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    result = repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )

    with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
        connection.execute(
            "UPDATE analysis_runs SET analyzer_kind = 'skills' WHERE id = ?",
            (str(result.analysis_run_id),),
        )
    connection.rollback()

    assert connection.execute(
        "SELECT analyzer_kind FROM analysis_runs WHERE id = ?",
        (str(result.analysis_run_id),),
    ).fetchone()[0] == "roles"
    assert repository.get_role_evidence(result.analysis_run_id) == (named_backend(),)


def test_skill_run_kind_cannot_change_after_evidence(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    run_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO analysis_runs (
            id, job_posting_id, analyzer_kind, taxonomy_version,
            extractor_version, input_hash, created_at
        ) VALUES (?, ?, 'skills', '2', '2', ?, ?)
        """,
        (run_id, str(posting_id), "e" * 64, "2026-08-21T12:00:00.000000Z"),
    )
    connection.execute("INSERT INTO skills VALUES ('python', 'Python')")
    connection.execute(
        """
        INSERT INTO job_skills VALUES (
            ?, 'python', 'Python', 'title', 'Python', 'Python Developer',
            'python.python', 'exact_alias', 'mentioned'
        )
        """,
        (run_id,),
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
        connection.execute(
            "UPDATE analysis_runs SET analyzer_kind = 'roles' WHERE id = ?",
            (run_id,),
        )
    connection.rollback()

    assert connection.execute(
        "SELECT analyzer_kind FROM analysis_runs WHERE id = ?", (run_id,)
    ).fetchone()[0] == "skills"
    assert connection.execute(
        "SELECT COUNT(*) FROM job_skills WHERE analysis_run_id = ?", (run_id,)
    ).fetchone()[0] == 1


def test_existing_evidence_cannot_be_moved_to_the_wrong_analyzer_kind(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    role_repository = SQLiteRoleIntelligenceRepository(connection)
    role_run = role_repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )
    skill_run_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO analysis_runs (
            id, job_posting_id, analyzer_kind, taxonomy_version,
            extractor_version, input_hash, created_at
        ) VALUES (?, ?, 'skills', '2', '2', ?, ?)
        """,
        (
            skill_run_id,
            str(posting_id),
            "9" * 64,
            "2026-08-21T12:00:01.000000Z",
        ),
    )
    connection.execute("INSERT INTO skills VALUES ('python', 'Python')")
    connection.execute(
        """
        INSERT INTO job_skills VALUES (
            ?, 'python', 'Python', 'title', 'Python', 'Python Developer',
            'python.python', 'exact_alias', 'mentioned'
        )
        """,
        (skill_run_id,),
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="roles analysis run"):
        connection.execute(
            "UPDATE job_roles SET analysis_run_id = ? WHERE analysis_run_id = ?",
            (skill_run_id, str(role_run.analysis_run_id)),
        )
    connection.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="skills analysis run"):
        connection.execute(
            "UPDATE job_skills SET analysis_run_id = ? WHERE analysis_run_id = ?",
            (str(role_run.analysis_run_id), skill_run_id),
        )
    connection.rollback()

    assert connection.execute(
        "SELECT analysis_run_id FROM job_roles"
    ).fetchone()[0] == str(role_run.analysis_run_id)
    assert connection.execute(
        "SELECT analysis_run_id FROM job_skills"
    ).fetchone()[0] == skill_run_id


@pytest.mark.parametrize(
    ("column", "replacement"),
    [
        ("job_posting_id", "00000000-0000-0000-0000-000000000000"),
        ("taxonomy_version", "future"),
        ("extractor_version", "future"),
        ("input_hash", "f" * 64),
    ],
)
def test_other_analysis_identity_fields_are_immutable(
    connection: sqlite3.Connection,
    column: str,
    replacement: str,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    result = repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )
    assert column in {
        "job_posting_id",
        "taxonomy_version",
        "extractor_version",
        "input_hash",
    }

    with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
        connection.execute(
            f"UPDATE analysis_runs SET {column} = ? WHERE id = ?",
            (replacement, str(result.analysis_run_id)),
        )
    connection.rollback()


def test_unicode_and_historical_names_round_trip(connection: sqlite3.Connection) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    original = named_backend("Бекенд")
    renamed = named_backend("Backend Engineering")
    first = repository.persist_role_analysis(
        key(posting_id, taxonomy_version="1", extractor_version="1"),
        (original,),
        created_at=CREATED_AT,
    )
    second = repository.persist_role_analysis(
        key(posting_id, taxonomy_version="2", extractor_version="2"),
        (renamed,),
        created_at=CREATED_AT + timedelta(days=1),
    )
    assert first.analysis_run_id != second.analysis_run_id

    assert repository.get_role_evidence(first.analysis_run_id) == (original,)
    assert repository.get_role_evidence(second.analysis_run_id) == (renamed,)
    assert connection.execute(
        "SELECT display_name FROM roles WHERE code = 'backend'"
    ).fetchone()[0] == "Бекенд"


def test_historical_names_do_not_depend_on_future_first_run_order(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    future_name = named_backend("Backend Engineering")
    original_name = named_backend("Backend")
    future = repository.persist_role_analysis(
        key(posting_id, taxonomy_version="2", extractor_version="2"),
        (future_name,),
        created_at=CREATED_AT,
    )
    original = repository.persist_role_analysis(
        key(posting_id, title="Backend Engineer v1 later"),
        (original_name,),
        created_at=CREATED_AT + timedelta(days=1),
    )

    assert repository.get_role_evidence(future.analysis_run_id) == (future_name,)
    assert repository.get_role_evidence(original.analysis_run_id) == (original_name,)
    assert connection.execute(
        "SELECT display_name FROM roles WHERE code = 'backend'"
    ).fetchone()[0] == "Backend Engineering"


def test_unicode_and_punctuation_evidence_round_trips_exactly(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    evidence = role_evidence(
        "community",
        "Спільнота & Community",
        matched_text="Community Manager – Україна",
    )
    result = repository.persist_role_analysis(
        key(posting_id, title="Community Manager – Україна"),
        (evidence,),
        created_at=CREATED_AT,
    )

    assert repository.get_role_evidence(result.analysis_run_id) == (evidence,)


def test_deleting_posting_cascades_only_role_derived_rows(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    repository = SQLiteRoleIntelligenceRepository(connection)
    result = repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )

    connection.execute("DELETE FROM job_postings WHERE id = ?", (str(posting_id),))
    connection.commit()

    assert repository.get_role_evidence(result.analysis_run_id) == ()
    assert connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM canonical_jobs").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 1


def test_deleting_derived_role_data_never_deletes_source_graph(
    connection: sqlite3.Connection,
) -> None:
    posting_id = insert_posting(connection)
    connection.execute(
        """
        INSERT INTO raw_jobs (
            id, job_posting_id, source_provider, source_scope, external_id,
            fetched_at, observation_hash, payload_json
        ) VALUES (?, ?, 'remote_ok', 'global', '1', ?, ?, ?)
        """,
        (
            str(uuid4()),
            str(posting_id),
            "2026-08-21T12:00:00.000000Z",
            "b" * 64,
            '{"title":"Backend Engineer"}',
        ),
    )
    connection.commit()
    repository = SQLiteRoleIntelligenceRepository(connection)
    result = repository.persist_role_analysis(
        key(posting_id), (named_backend(),), created_at=CREATED_AT
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("DELETE FROM roles WHERE code = 'backend'")
    connection.rollback()

    connection.execute(
        "DELETE FROM analysis_runs WHERE id = ?", (str(result.analysis_run_id),)
    )
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM canonical_jobs").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0] == 1

    connection.execute("DELETE FROM roles WHERE code = 'backend'")
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM canonical_jobs").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0] == 1
