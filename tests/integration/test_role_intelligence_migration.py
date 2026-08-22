import sqlite3
from uuid import uuid4

import pytest

import job_market_analyzer.storage.sqlite as sqlite_storage
from job_market_analyzer.storage.sqlite import (
    CURRENT_SCHEMA_VERSION,
    InconsistentDatabaseSchemaError,
    connect_database,
    initialize_database,
    load_intelligence_schema,
    load_role_intelligence_schema,
    load_schema,
)

NOW = "2026-08-21T10:00:00.000000Z"


def create_v2_with_source_and_skill(connection: sqlite3.Connection) -> dict[str, str]:
    connection.executescript(load_schema())
    connection.executescript(load_intelligence_schema())
    ids = {
        name: str(uuid4())
        for name in ("canonical", "posting", "raw", "run")
    }
    connection.execute(
        "INSERT INTO canonical_jobs (id, created_at, updated_at) VALUES (?, ?, ?)",
        (ids["canonical"], NOW, NOW),
    )
    connection.execute(
        """
        INSERT INTO job_postings (
            id, canonical_job_id, source_provider, source_scope, external_id,
            title, first_seen_at, last_seen_at, content_hash,
            latest_observation_hash
        ) VALUES (?, ?, 'remote_ok', 'global', 'legacy', 'Python Developer',
                  ?, ?, ?, ?)
        """,
        (ids["posting"], ids["canonical"], NOW, NOW, "a" * 64, "b" * 64),
    )
    connection.execute(
        """
        INSERT INTO raw_jobs (
            id, job_posting_id, source_provider, source_scope, external_id,
            fetched_at, observation_hash, payload_json
        ) VALUES (?, ?, 'remote_ok', 'global', 'legacy', ?, ?, ?)
        """,
        (ids["raw"], ids["posting"], NOW, "b" * 64, '{"title":"Python Developer"}'),
    )
    connection.execute(
        """
        INSERT INTO analysis_runs (
            id, job_posting_id, analyzer_kind, taxonomy_version,
            extractor_version, input_hash, created_at
        ) VALUES (?, ?, 'skills', '2', '2', ?, ?)
        """,
        (ids["run"], ids["posting"], "c" * 64, NOW),
    )
    connection.execute("INSERT INTO skills VALUES ('python', 'Python')")
    connection.execute(
        """
        INSERT INTO job_skills VALUES (
            ?, 'python', 'Python', 'title', 'Python', 'Python Developer',
            'python.python', 'exact_alias', 'mentioned'
        )
        """,
        (ids["run"],),
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    return ids


def snapshot(connection: sqlite3.Connection) -> dict[str, list[dict[str, object]]]:
    return {
        table: [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]
        for table in (
            "canonical_jobs",
            "job_postings",
            "raw_jobs",
            "analysis_runs",
            "skills",
            "job_skills",
        )
    }


def promote_to_v3_with_schema(
    connection: sqlite3.Connection,
    role_schema: str,
) -> None:
    create_v2_with_source_and_skill(connection)
    connection.executescript(role_schema)
    connection.execute("PRAGMA user_version = 3")
    connection.commit()


def test_valid_v2_migrates_without_backfill_and_preserves_everything() -> None:
    connection = connect_database(":memory:")
    try:
        ids = create_v2_with_source_and_skill(connection)
        before = snapshot(connection)

        initialize_database(connection)
        initialize_database(connection)

        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        assert snapshot(connection) == before
        assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM job_roles").fetchone()[0] == 0
        # The additive seniority migration creates its structures without
        # touching role or source rows.
        assert connection.execute(
            "SELECT COUNT(*) FROM seniority_levels"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM job_seniority"
        ).fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT id FROM analysis_runs WHERE id = ?", (ids["run"],)
        ).fetchone()[0] == ids["run"]
    finally:
        connection.close()


def test_role_migration_failure_rolls_back_and_retry_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = connect_database(":memory:")
    try:
        create_v2_with_source_and_skill(connection)
        before = snapshot(connection)
        valid_schema = load_role_intelligence_schema()
        malformed = valid_schema.replace("    role_name TEXT NOT NULL,\n", "").replace(
            "    CHECK (length(trim(role_name)) > 0),\n", ""
        )
        monkeypatch.setattr(
            sqlite_storage, "load_role_intelligence_schema", lambda: malformed
        )

        with pytest.raises(
            InconsistentDatabaseSchemaError, match="missing columns: role_name"
        ):
            initialize_database(connection)

        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'trigger')"
            )
        }
        assert not objects.intersection(
            {
                "roles",
                "job_roles",
                "trg_analysis_runs_identity_immutable",
                "trg_job_roles_roles_kind",
                "trg_job_roles_roles_kind_update",
                "trg_job_skills_skills_kind",
                "trg_job_skills_skills_kind_update",
            }
        )
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert snapshot(connection) == before
        assert connection.in_transaction is False

        monkeypatch.setattr(
            sqlite_storage, "load_role_intelligence_schema", lambda: valid_schema
        )
        initialize_database(connection)
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == CURRENT_SCHEMA_VERSION
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_v2_cross_kind_skill_evidence_is_rejected_without_partial_v3() -> None:
    connection = connect_database(":memory:")
    try:
        ids = create_v2_with_source_and_skill(connection)
        connection.execute(
            "UPDATE analysis_runs SET analyzer_kind = 'roles' WHERE id = ?",
            (ids["run"],),
        )
        connection.commit()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="job_skills.*non-skills analysis run",
        ):
            initialize_database(connection)

        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert "roles" not in {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert connection.execute(
            "SELECT analyzer_kind FROM analysis_runs WHERE id = ?", (ids["run"],)
        ).fetchone()[0] == "roles"
    finally:
        connection.close()


def test_partial_role_schema_at_v2_is_rejected_without_mutation() -> None:
    connection = connect_database(":memory:")
    try:
        create_v2_with_source_and_skill(connection)
        connection.execute(
            "CREATE TABLE roles (code TEXT PRIMARY KEY, display_name TEXT NOT NULL)"
        )
        connection.commit()
        before = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="unexpected partial role-intelligence objects: roles",
        ):
            initialize_database(connection)

        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall() == before
        assert connection.in_transaction is False
    finally:
        connection.close()


def test_incomplete_v3_is_rejected() -> None:
    connection = connect_database(":memory:")
    try:
        create_v2_with_source_and_skill(connection)
        connection.executescript(load_role_intelligence_schema())
        connection.execute("DROP TABLE job_roles")
        connection.execute("PRAGMA user_version = 3")
        connection.commit()

        with pytest.raises(
            InconsistentDatabaseSchemaError, match="missing tables: job_roles"
        ):
            initialize_database(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.in_transaction is False
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("malformed_schema", "expected_error"),
    [
        (
            load_role_intelligence_schema()
            .replace("    role_name TEXT NOT NULL,\n", "")
            .replace("    CHECK (length(trim(role_name)) > 0),\n", ""),
            "missing columns: role_name",
        ),
        (
            load_role_intelligence_schema().replace(
                "REFERENCES analysis_runs(id)", "REFERENCES canonical_jobs(id)"
            ),
            "missing foreign key",
        ),
        (
            load_role_intelligence_schema().replace(
                """PRIMARY KEY (
        analysis_run_id,
        role_code
    )""",
                """PRIMARY KEY (
        analysis_run_id,
        role_code,
        evidence_field
    )""",
            ),
            "invalid primary key",
        ),
        (
            load_role_intelligence_schema().replace(
                "code TEXT NOT NULL PRIMARY KEY", "code TEXT NOT NULL"
            ),
            "invalid foreign key structure",
        ),
    ],
)
def test_malformed_v3_role_structures_are_rejected(
    malformed_schema: str,
    expected_error: str,
) -> None:
    connection = connect_database(":memory:")
    try:
        promote_to_v3_with_schema(connection, malformed_schema)
        with pytest.raises(InconsistentDatabaseSchemaError, match=expected_error):
            initialize_database(connection)
        assert connection.in_transaction is False
    finally:
        connection.close()


@pytest.mark.parametrize(
    "trigger_name",
    [
        "trg_analysis_runs_identity_immutable",
        "trg_job_roles_roles_kind",
        "trg_job_roles_roles_kind_update",
        "trg_job_skills_skills_kind",
        "trg_job_skills_skills_kind_update",
    ],
)
def test_v3_missing_required_trigger_is_rejected(trigger_name: str) -> None:
    connection = connect_database(":memory:")
    try:
        promote_to_v3_with_schema(connection, load_role_intelligence_schema())
        connection.execute(f"DROP TRIGGER {trigger_name}")
        connection.commit()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match=f"missing trigger {trigger_name!r}",
        ):
            initialize_database(connection)
        assert connection.in_transaction is False
    finally:
        connection.close()


def test_v3_rejects_identity_trigger_with_incomplete_update_scope() -> None:
    connection = connect_database(":memory:")
    try:
        promote_to_v3_with_schema(connection, load_role_intelligence_schema())
        connection.execute("DROP TRIGGER trg_analysis_runs_identity_immutable")
        connection.execute(
            """
            CREATE TRIGGER trg_analysis_runs_identity_immutable
            BEFORE UPDATE OF analyzer_kind ON analysis_runs
            BEGIN
                SELECT RAISE(ABORT, 'analysis run identity is immutable');
            END
            """
        )
        connection.commit()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="required semantics.*job_posting_id",
        ):
            initialize_database(connection)
    finally:
        connection.close()


def test_v3_rejects_role_trigger_with_cosmetic_name_and_message_only() -> None:
    connection = connect_database(":memory:")
    try:
        promote_to_v3_with_schema(connection, load_role_intelligence_schema())
        connection.execute("DROP TRIGGER trg_job_roles_roles_kind")
        connection.execute(
            """
            CREATE TRIGGER trg_job_roles_roles_kind
            BEFORE INSERT ON job_roles
            BEGIN
                SELECT RAISE(ABORT, 'job_roles requires a roles analysis run');
            END
            """
        )
        connection.commit()

        with pytest.raises(
            InconsistentDatabaseSchemaError,
            match="required semantics.*where id = new.analysis_run_id",
        ):
            initialize_database(connection)
    finally:
        connection.close()
