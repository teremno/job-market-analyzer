import sqlite3
from importlib import resources
from pathlib import Path

from job_market_analyzer.models import NormalizedJobPosting
from job_market_analyzer.storage.serialization import (
    calculate_content_hash,
    deserialize_source_tags,
)

DatabasePath = str | Path
SOURCE_TAGS_SCHEMA_VERSION = 1
SKILL_INTELLIGENCE_SCHEMA_VERSION = 2
ROLE_INTELLIGENCE_SCHEMA_VERSION = 3
SENIORITY_INTELLIGENCE_SCHEMA_VERSION = 4
GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION = 5
CURRENT_SCHEMA_VERSION = GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION
_SKILL_INTELLIGENCE_OBJECTS = frozenset(
    {
        "analysis_runs",
        "idx_analysis_runs_posting_kind_created",
        "idx_job_skills_skill_run",
        "job_skills",
        "skills",
    }
)
_ROLE_INTELLIGENCE_OBJECTS = frozenset(
    {
        "idx_job_roles_role_run",
        "job_roles",
        "roles",
        "trg_analysis_runs_identity_immutable",
        "trg_job_roles_roles_kind",
        "trg_job_roles_roles_kind_update",
        "trg_job_skills_skills_kind",
        "trg_job_skills_skills_kind_update",
    }
)
_SENIORITY_INTELLIGENCE_OBJECTS = frozenset(
    {
        "idx_job_seniority_level_run",
        "job_seniority",
        "seniority_levels",
        "trg_job_seniority_levels_kind",
        "trg_job_seniority_levels_kind_update",
    }
)
_GEOGRAPHY_INTELLIGENCE_OBJECTS = frozenset(
    {
        "geography_terms",
        "idx_job_geography_term_run",
        "job_geography",
        "trg_job_geography_terms_kind",
        "trg_job_geography_terms_kind_update",
    }
)


class DatabaseSchemaError(RuntimeError):
    """Base error for an unsupported or inconsistent SQLite schema."""


class UnsupportedDatabaseSchemaVersionError(DatabaseSchemaError):
    """Raised when a database was created by a newer application version."""


class InconsistentDatabaseSchemaError(DatabaseSchemaError):
    """Raised when the declared schema version does not match its structure."""


def load_schema() -> str:
    """Load the packaged SQLite schema."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "schema.sql"
    )

    return schema_file.read_text(encoding="utf-8")


def load_intelligence_schema() -> str:
    """Load the additive SQLite schema for derived intelligence."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "intelligence_schema.sql"
    )

    return schema_file.read_text(encoding="utf-8")


def load_role_intelligence_schema() -> str:
    """Load the additive SQLite schema for role intelligence."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "role_intelligence_schema.sql"
    )
    return schema_file.read_text(encoding="utf-8")


def load_seniority_intelligence_schema() -> str:
    """Load the additive SQLite schema for seniority intelligence."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "seniority_intelligence_schema.sql"
    )
    return schema_file.read_text(encoding="utf-8")


def load_geography_intelligence_schema() -> str:
    """Load the additive SQLite schema for geography intelligence."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "geography_intelligence_schema.sql"
    )
    return schema_file.read_text(encoding="utf-8")


def connect_database(
    database_path: DatabasePath,
) -> sqlite3.Connection:
    """
    Open a configured SQLite connection.

    The database path is provided by the caller so the storage layer
    does not depend on a specific machine, operating system, or
    filesystem layout.
    """

    connection = sqlite3.connect(str(database_path))

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    if str(database_path) != ":memory:":
        connection.execute("PRAGMA journal_mode = WAL")

    return connection


def connect_read_only_database(
    database_path: DatabasePath,
) -> sqlite3.Connection:
    """Open an existing SQLite file without allowing writes or file creation."""

    resolved_path = Path(database_path).resolve(strict=True)
    if not resolved_path.is_file():
        raise FileNotFoundError("SQLite database path is not a file")

    connection = sqlite3.connect(
        f"{resolved_path.as_uri()}?mode=ro",
        uri=True,
        check_same_thread=False,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA query_only = ON")
    except Exception:
        connection.close()
        raise
    return connection


def initialize_database(
    connection: sqlite3.Connection,
) -> None:
    """Create the schema and apply small backward-compatible MVP migrations."""

    if connection.in_transaction:
        raise RuntimeError(
            "initialize_database must be called outside an active transaction"
        )

    initial_version = _get_schema_version(connection)
    if initial_version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedDatabaseSchemaVersionError(
            "Database schema version "
            f"{initial_version} is newer than supported version "
            f"{CURRENT_SCHEMA_VERSION}"
        )

    if initial_version == CURRENT_SCHEMA_VERSION:
        _validate_v5_schema(connection)
        return

    if initial_version == SENIORITY_INTELLIGENCE_SCHEMA_VERSION:
        _validate_v4_schema(connection)
        _validate_no_partial_geography_schema(connection, initial_version)
    elif initial_version == ROLE_INTELLIGENCE_SCHEMA_VERSION:
        _validate_v3_schema(connection)
    elif initial_version == SKILL_INTELLIGENCE_SCHEMA_VERSION:
        _validate_v2_schema(connection)
        _validate_no_partial_role_schema(connection, initial_version)
        if _requires_role_intelligence_migration(connection):
            _migrate_role_intelligence(connection)
        _validate_v3_schema(connection)
    else:
        _validate_no_partial_intelligence_schema(connection, initial_version)

        if initial_version == SOURCE_TAGS_SCHEMA_VERSION:
            _validate_source_schema(connection, version=initial_version)
        else:
            _create_source_schema(connection)

        if _requires_nullable_source_url_migration(connection):
            _migrate_nullable_source_urls(connection)
        if _requires_source_tags_migration(connection):
            _migrate_source_tags(connection)

        _validate_source_schema(connection, version=SOURCE_TAGS_SCHEMA_VERSION)
        if _requires_skill_intelligence_migration(connection):
            _migrate_skill_intelligence(connection)
        _validate_v2_schema(connection)
        if _requires_role_intelligence_migration(connection):
            _migrate_role_intelligence(connection)
        _validate_v3_schema(connection)

    if _requires_seniority_intelligence_migration(connection):
        _migrate_seniority_intelligence(connection)

    _validate_v4_schema(connection)

    if _requires_geography_intelligence_migration(connection):
        _migrate_geography_intelligence(connection)

    _validate_v5_schema(connection)


def _create_source_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.executescript(f"BEGIN IMMEDIATE;\n{load_schema()}\nCOMMIT;")
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _get_schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _validate_no_partial_intelligence_schema(
    connection: sqlite3.Connection,
    version: int,
) -> None:
    unexpected = _schema_object_names(connection) & (
        _SKILL_INTELLIGENCE_OBJECTS
        | _ROLE_INTELLIGENCE_OBJECTS
        | _SENIORITY_INTELLIGENCE_OBJECTS
        | _GEOGRAPHY_INTELLIGENCE_OBJECTS
    )
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} contains unexpected partial "
            f"intelligence tables: {names}"
        )


def _validate_no_partial_role_schema(
    connection: sqlite3.Connection,
    version: int,
) -> None:
    unexpected = _schema_object_names(connection) & (
        _ROLE_INTELLIGENCE_OBJECTS | _SENIORITY_INTELLIGENCE_OBJECTS
    )
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} contains unexpected partial "
            f"role-intelligence objects: {names}"
        )


def _validate_no_partial_geography_schema(
    connection: sqlite3.Connection,
    version: int,
) -> None:
    unexpected = _schema_object_names(connection) & (
        _GEOGRAPHY_INTELLIGENCE_OBJECTS
    )
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} contains unexpected partial "
            f"geography objects: {names}"
        )


def _validate_source_schema(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    expected_columns = {
        "canonical_jobs": {"id", "created_at", "updated_at"},
        "job_postings": {
            "id",
            "canonical_job_id",
            "source_provider",
            "source_scope",
            "external_id",
            "source_url",
            "application_url",
            "title",
            "company_name",
            "description_text",
            "source_tags_json",
            "location_text",
            "is_remote",
            "remote_scope",
            "employment_type",
            "salary_text",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_period",
            "published_at",
            "source_updated_at",
            "first_seen_at",
            "last_seen_at",
            "content_hash",
            "latest_observation_hash",
        },
        "raw_jobs": {
            "id",
            "job_posting_id",
            "source_provider",
            "source_scope",
            "external_id",
            "source_url",
            "fetched_at",
            "observation_hash",
            "payload_json",
        },
    }
    _require_tables(connection, set(expected_columns), version=version)
    for table_name, columns in expected_columns.items():
        _require_columns(connection, table_name, columns, version=version)

    _require_primary_key(connection, "canonical_jobs", ("id",), version=version)
    _require_primary_key(connection, "job_postings", ("id",), version=version)
    _require_primary_key(connection, "raw_jobs", ("id",), version=version)
    _require_unique_columns(
        connection,
        "job_postings",
        ("source_provider", "source_scope", "external_id"),
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_postings",
        from_column="canonical_job_id",
        target_table="canonical_jobs",
        target_column="id",
        on_delete="RESTRICT",
        version=version,
    )
    _require_foreign_key(
        connection,
        "raw_jobs",
        from_column="job_posting_id",
        target_table="job_postings",
        target_column="id",
        on_delete="RESTRICT",
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_job_postings_canonical_job_id",
        ("canonical_job_id",),
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_raw_jobs_posting_fetched_at",
        ("job_posting_id", "fetched_at"),
        version=version,
    )
    _require_foreign_keys_enabled(connection, version=version)
    _require_no_foreign_key_violations(connection, version=version)


def _validate_v2_schema(connection: sqlite3.Connection) -> None:
    version = _get_schema_version(connection)
    if version != SKILL_INTELLIGENCE_SCHEMA_VERSION:
        raise InconsistentDatabaseSchemaError(
            "Expected database schema version "
            f"{SKILL_INTELLIGENCE_SCHEMA_VERSION}, got {version}"
        )

    _validate_source_schema(connection, version=version)
    _validate_intelligence_schema(connection, version=version)


def _validate_v3_schema(connection: sqlite3.Connection) -> None:
    version = _get_schema_version(connection)
    if version != ROLE_INTELLIGENCE_SCHEMA_VERSION:
        raise InconsistentDatabaseSchemaError(
            "Expected database schema version "
            f"{ROLE_INTELLIGENCE_SCHEMA_VERSION}, got {version}"
        )

    _validate_source_schema(connection, version=version)
    _validate_intelligence_schema(connection, version=version)
    _validate_role_intelligence_schema(connection, version=version)


def _validate_v4_schema(connection: sqlite3.Connection) -> None:
    version = _get_schema_version(connection)
    if version != SENIORITY_INTELLIGENCE_SCHEMA_VERSION:
        raise InconsistentDatabaseSchemaError(
            "Expected database schema version "
            f"{SENIORITY_INTELLIGENCE_SCHEMA_VERSION}, got {version}"
        )

    _validate_source_schema(connection, version=version)
    _validate_intelligence_schema(connection, version=version)
    _validate_role_intelligence_schema(connection, version=version)
    _validate_seniority_intelligence_schema(connection, version=version)


def _validate_v5_schema(connection: sqlite3.Connection) -> None:
    version = _get_schema_version(connection)
    if version != GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION:
        raise InconsistentDatabaseSchemaError(
            "Expected database schema version "
            f"{GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION}, got {version}"
        )

    _validate_source_schema(connection, version=version)
    _validate_intelligence_schema(connection, version=version)
    _validate_role_intelligence_schema(connection, version=version)
    _validate_seniority_intelligence_schema(connection, version=version)
    _validate_geography_intelligence_schema(connection, version=version)


def _validate_intelligence_schema(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    expected_columns = {
        "skills": {"code", "display_name"},
        "analysis_runs": {
            "id",
            "job_posting_id",
            "analyzer_kind",
            "taxonomy_version",
            "extractor_version",
            "input_hash",
            "created_at",
        },
        "job_skills": {
            "analysis_run_id",
            "skill_code",
            "skill_name",
            "evidence_field",
            "matched_alias",
            "evidence_text",
            "rule_id",
            "match_kind",
            "mention_kind",
        },
    }
    _require_tables(connection, set(expected_columns), version=version)
    for table_name, columns in expected_columns.items():
        _require_columns(
            connection,
            table_name,
            columns,
            version=version,
            require_not_null=True,
        )

    _require_primary_key(connection, "skills", ("code",), version=version)
    _require_primary_key(connection, "analysis_runs", ("id",), version=version)
    _require_primary_key(
        connection,
        "job_skills",
        ("analysis_run_id", "skill_code", "evidence_field"),
        version=version,
    )
    _require_unique_columns(
        connection,
        "analysis_runs",
        (
            "job_posting_id",
            "analyzer_kind",
            "taxonomy_version",
            "extractor_version",
            "input_hash",
        ),
        version=version,
    )
    _require_foreign_key(
        connection,
        "analysis_runs",
        from_column="job_posting_id",
        target_table="job_postings",
        target_column="id",
        on_delete="CASCADE",
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_skills",
        from_column="analysis_run_id",
        target_table="analysis_runs",
        target_column="id",
        on_delete="CASCADE",
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_skills",
        from_column="skill_code",
        target_table="skills",
        target_column="code",
        on_delete="RESTRICT",
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_analysis_runs_posting_kind_created",
        ("job_posting_id", "analyzer_kind", "created_at"),
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_job_skills_skill_run",
        ("skill_code", "analysis_run_id"),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "analysis_runs",
        (
            "length(input_hash) = 64",
            "input_hash not glob '*[^0-9a-f]*'",
        ),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "job_skills",
        (
            "length(trim(skill_name)) > 0",
            "evidence_field in ('title', 'description', 'tag')",
            "match_kind in ('exact_alias', 'contextual')",
            "mention_kind = 'mentioned'",
        ),
        version=version,
    )
    _require_no_foreign_key_violations(connection, version=version)


def _validate_role_intelligence_schema(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    expected_columns = {
        "roles": {"code", "display_name"},
        "job_roles": {
            "analysis_run_id",
            "role_code",
            "role_name",
            "evidence_field",
            "matched_text",
            "evidence_text",
            "rule_id",
            "match_kind",
        },
    }
    _require_tables(connection, set(expected_columns), version=version)
    for table_name, columns in expected_columns.items():
        _require_columns(
            connection,
            table_name,
            columns,
            version=version,
            require_not_null=True,
        )

    _require_primary_key(connection, "roles", ("code",), version=version)
    _require_table_sql_fragments(
        connection,
        "roles",
        (
            "length(trim(code)) > 0",
            "length(trim(display_name)) > 0",
        ),
        version=version,
    )
    _require_primary_key(
        connection,
        "job_roles",
        ("analysis_run_id", "role_code"),
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_roles",
        from_column="analysis_run_id",
        target_table="analysis_runs",
        target_column="id",
        on_delete="CASCADE",
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_roles",
        from_column="role_code",
        target_table="roles",
        target_column="code",
        on_delete="RESTRICT",
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_job_roles_role_run",
        ("role_code", "analysis_run_id"),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "job_roles",
        (
            "evidence_field in ('title', 'description')",
            "length(trim(role_name)) > 0",
            "length(trim(matched_text)) > 0",
            "length(trim(evidence_text)) > 0",
            "length(trim(rule_id)) > 0",
            "match_kind in ('title_pattern', 'description_statement')",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_analysis_runs_identity_immutable",
        (
            "before update of job_posting_id, analyzer_kind, taxonomy_version, "
            "extractor_version, input_hash on analysis_runs",
            "analysis run identity is immutable",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_roles_roles_kind",
        (
            "before insert on job_roles",
            "where id = new.analysis_run_id",
            "!= 'roles'",
            "job_roles requires a roles analysis run",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_skills_skills_kind",
        (
            "before insert on job_skills",
            "where id = new.analysis_run_id",
            "!= 'skills'",
            "job_skills requires a skills analysis run",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_roles_roles_kind_update",
        (
            "before update of analysis_run_id on job_roles",
            "where id = new.analysis_run_id",
            "!= 'roles'",
            "job_roles requires a roles analysis run",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_skills_skills_kind_update",
        (
            "before update of analysis_run_id on job_skills",
            "where id = new.analysis_run_id",
            "!= 'skills'",
            "job_skills requires a skills analysis run",
        ),
        version=version,
    )
    _require_evidence_analyzer_kind(
        connection,
        evidence_table="job_roles",
        expected_kind="roles",
        version=version,
    )
    _require_evidence_analyzer_kind(
        connection,
        evidence_table="job_skills",
        expected_kind="skills",
        version=version,
    )
    _require_no_foreign_key_violations(connection, version=version)


def _validate_seniority_intelligence_schema(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    expected_columns = {
        "seniority_levels": {"code", "display_name"},
        "job_seniority": {
            "analysis_run_id",
            "seniority_code",
            "seniority_name",
            "evidence_field",
            "matched_text",
            "evidence_text",
            "rule_id",
            "match_kind",
        },
    }
    _require_tables(connection, set(expected_columns), version=version)
    for table_name, columns in expected_columns.items():
        _require_columns(
            connection,
            table_name,
            columns,
            version=version,
            require_not_null=True,
        )

    _require_primary_key(
        connection,
        "seniority_levels",
        ("code",),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "seniority_levels",
        (
            "length(trim(code)) > 0",
            "length(trim(display_name)) > 0",
        ),
        version=version,
    )
    _require_primary_key(
        connection,
        "job_seniority",
        ("analysis_run_id", "seniority_code"),
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_seniority",
        from_column="analysis_run_id",
        target_table="analysis_runs",
        target_column="id",
        on_delete="CASCADE",
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_seniority",
        from_column="seniority_code",
        target_table="seniority_levels",
        target_column="code",
        on_delete="RESTRICT",
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_job_seniority_level_run",
        ("seniority_code", "analysis_run_id"),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "job_seniority",
        (
            "evidence_field in ('title', 'description')",
            "length(trim(seniority_name)) > 0",
            "length(trim(matched_text)) > 0",
            "length(trim(evidence_text)) > 0",
            "length(trim(rule_id)) > 0",
            "match_kind in ('title_pattern', 'description_statement')",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_seniority_levels_kind",
        (
            "before insert on job_seniority",
            "where id = new.analysis_run_id",
            "!= 'seniority'",
            "job_seniority requires a seniority analysis run",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_seniority_levels_kind_update",
        (
            "before update of analysis_run_id on job_seniority",
            "where id = new.analysis_run_id",
            "!= 'seniority'",
            "job_seniority requires a seniority analysis run",
        ),
        version=version,
    )
    _require_evidence_analyzer_kind(
        connection,
        evidence_table="job_seniority",
        expected_kind="seniority",
        version=version,
    )
    _require_no_foreign_key_violations(connection, version=version)


def _validate_geography_intelligence_schema(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    expected_columns = {
        "geography_terms": {"code", "display_name", "dimension"},
        "job_geography": {
            "analysis_run_id",
            "geography_code",
            "geography_name",
            "dimension",
            "evidence_field",
            "matched_text",
            "evidence_text",
            "rule_id",
            "match_kind",
        },
    }
    _require_tables(connection, set(expected_columns), version=version)
    for table_name, columns in expected_columns.items():
        _require_columns(
            connection,
            table_name,
            columns,
            version=version,
            require_not_null=True,
        )

    _require_primary_key(
        connection,
        "geography_terms",
        ("code",),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "geography_terms",
        (
            "length(trim(code)) > 0",
            "length(trim(display_name)) > 0",
            "dimension in ('arrangement', 'region')",
        ),
        version=version,
    )
    _require_primary_key(
        connection,
        "job_geography",
        ("analysis_run_id", "geography_code"),
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_geography",
        from_column="analysis_run_id",
        target_table="analysis_runs",
        target_column="id",
        on_delete="CASCADE",
        version=version,
    )
    _require_foreign_key(
        connection,
        "job_geography",
        from_column="geography_code",
        target_table="geography_terms",
        target_column="code",
        on_delete="RESTRICT",
        version=version,
    )
    _require_index_columns(
        connection,
        "idx_job_geography_term_run",
        ("geography_code", "analysis_run_id"),
        version=version,
    )
    _require_table_sql_fragments(
        connection,
        "job_geography",
        (
            "dimension in ('arrangement', 'region')",
            "evidence_field in ('description', 'location', 'structured')",
            "length(trim(geography_name)) > 0",
            "length(trim(matched_text)) > 0",
            "length(trim(evidence_text)) > 0",
            "length(trim(rule_id)) > 0",
            "match_kind in ('title_pattern', 'description_statement',"
            " 'normalized_field')",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_geography_terms_kind",
        (
            "before insert on job_geography",
            "where id = new.analysis_run_id",
            "!= 'geography'",
            "job_geography requires a geography analysis run",
        ),
        version=version,
    )
    _require_trigger_sql_fragment(
        connection,
        "trg_job_geography_terms_kind_update",
        (
            "before update of analysis_run_id on job_geography",
            "where id = new.analysis_run_id",
            "!= 'geography'",
            "job_geography requires a geography analysis run",
        ),
        version=version,
    )
    _require_evidence_analyzer_kind(
        connection,
        evidence_table="job_geography",
        expected_kind="geography",
        version=version,
    )
    _require_no_foreign_key_violations(connection, version=version)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _schema_object_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table', 'index', 'trigger')"
        )
    }


def _pragma_rows(
    connection: sqlite3.Connection,
    pragma_name: str,
    object_name: str,
) -> list[sqlite3.Row]:
    if not object_name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe SQLite schema identifier: {object_name!r}")
    return connection.execute(
        f"PRAGMA {pragma_name}('{object_name}')"
    ).fetchall()


def _require_tables(
    connection: sqlite3.Connection,
    expected: set[str],
    *,
    version: int,
) -> None:
    missing = expected - _table_names(connection)
    if missing:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} is missing tables: "
            + ", ".join(sorted(missing))
        )


def _require_columns(
    connection: sqlite3.Connection,
    table_name: str,
    expected: set[str],
    *,
    version: int,
    require_not_null: bool = False,
) -> None:
    rows = _pragma_rows(connection, "table_info", table_name)
    by_name = {row["name"]: row for row in rows}
    missing = expected - set(by_name)
    if missing:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} table {table_name!r} is missing "
            f"columns: {', '.join(sorted(missing))}"
        )
    if require_not_null:
        nullable = sorted(
            column for column in expected if not by_name[column]["notnull"]
        )
        if nullable:
            raise InconsistentDatabaseSchemaError(
                f"Database schema version {version} table {table_name!r} has "
                f"nullable critical columns: {', '.join(nullable)}"
            )


def _require_primary_key(
    connection: sqlite3.Connection,
    table_name: str,
    expected: tuple[str, ...],
    *,
    version: int,
) -> None:
    rows = _pragma_rows(connection, "table_info", table_name)
    actual = tuple(
        row["name"]
        for row in sorted(rows, key=lambda row: row["pk"])
        if row["pk"]
    )
    if actual != expected:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} table {table_name!r} has invalid "
            f"primary key {actual!r}; expected {expected!r}"
        )


def _index_columns(
    connection: sqlite3.Connection,
    index_name: str,
) -> tuple[str, ...]:
    return tuple(
        row["name"]
        for row in _pragma_rows(connection, "index_info", index_name)
    )


def _require_unique_columns(
    connection: sqlite3.Connection,
    table_name: str,
    expected: tuple[str, ...],
    *,
    version: int,
) -> None:
    unique_indexes = [
        row["name"]
        for row in _pragma_rows(connection, "index_list", table_name)
        if row["unique"]
    ]
    if not any(
        _index_columns(connection, index_name) == expected
        for index_name in unique_indexes
    ):
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} table {table_name!r} is missing "
            f"unique columns {expected!r}"
        )


def _require_index_columns(
    connection: sqlite3.Connection,
    index_name: str,
    expected: tuple[str, ...],
    *,
    version: int,
) -> None:
    actual = _index_columns(connection, index_name)
    if actual != expected:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} is missing index {index_name!r} "
            f"with columns {expected!r}"
        )


def _require_foreign_key(
    connection: sqlite3.Connection,
    table_name: str,
    *,
    from_column: str,
    target_table: str,
    target_column: str,
    on_delete: str,
    version: int,
) -> None:
    expected = (from_column, target_table, target_column, on_delete)
    actual = {
        (row["from"], row["table"], row["to"], row["on_delete"])
        for row in _pragma_rows(connection, "foreign_key_list", table_name)
    }
    if expected not in actual:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} table {table_name!r} is missing "
            f"foreign key {expected!r}"
        )


def _require_table_sql_fragments(
    connection: sqlite3.Connection,
    table_name: str,
    expected: tuple[str, ...],
    *,
    version: int,
) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    normalized_sql = " ".join(row["sql"].lower().split()) if row else ""
    missing = [fragment for fragment in expected if fragment not in normalized_sql]
    if missing:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} table {table_name!r} is missing "
            f"critical constraints: {', '.join(missing)}"
        )


def _require_trigger_sql_fragment(
    connection: sqlite3.Connection,
    trigger_name: str,
    expected: str | tuple[str, ...],
    *,
    version: int,
) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        (trigger_name,),
    ).fetchone()
    normalized_sql = " ".join(row["sql"].lower().split()) if row else ""
    expected_fragments = (expected,) if isinstance(expected, str) else expected
    missing = [
        fragment for fragment in expected_fragments if fragment not in normalized_sql
    ]
    if missing:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} is missing trigger "
            f"{trigger_name!r} with required semantics: {', '.join(missing)}"
        )


def _require_evidence_analyzer_kind(
    connection: sqlite3.Connection,
    *,
    evidence_table: str,
    expected_kind: str,
    version: int,
) -> None:
    if evidence_table not in {"job_roles", "job_skills", "job_seniority", "job_geography"}:
        raise ValueError(f"Unsupported evidence table: {evidence_table!r}")
    invalid = connection.execute(
        f"""
        SELECT 1
        FROM {evidence_table}
        JOIN analysis_runs
          ON analysis_runs.id = {evidence_table}.analysis_run_id
        WHERE analysis_runs.analyzer_kind != ?
        LIMIT 1
        """,
        (expected_kind,),
    ).fetchone()
    if invalid is not None:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} table {evidence_table!r} "
            f"contains evidence for a non-{expected_kind} analysis run"
        )


def _require_foreign_keys_enabled(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} requires PRAGMA foreign_keys = ON"
        )


def _require_no_foreign_key_violations(
    connection: sqlite3.Connection,
    *,
    version: int,
) -> None:
    try:
        violation = connection.execute("PRAGMA foreign_key_check").fetchone()
    except sqlite3.DatabaseError as error:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} contains invalid foreign key "
            f"structure: {error}"
        ) from error
    if violation is not None:
        raise InconsistentDatabaseSchemaError(
            f"Database schema version {version} contains foreign key violations"
        )


def _requires_nullable_source_url_migration(
    connection: sqlite3.Connection,
) -> bool:
    for table_name in ("job_postings", "raw_jobs"):
        columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        source_url = next(row for row in columns if row[1] == "source_url")
        if source_url[3] == 1:
            return True
    return False


def _migrate_nullable_source_urls(connection: sqlite3.Connection) -> None:
    """Rebuild the two source tables so existing databases preserve all rows."""

    schema = load_schema()
    foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    connection.execute("PRAGMA foreign_keys = OFF")

    try:
        connection.executescript(
            f"""
            BEGIN IMMEDIATE;

            ALTER TABLE raw_jobs RENAME TO _raw_jobs_source_url_required;
            ALTER TABLE job_postings RENAME TO _job_postings_source_url_required;

            {schema}

            INSERT INTO job_postings (
                id,
                canonical_job_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                application_url,
                title,
                company_name,
                description_text,
                source_tags_json,
                location_text,
                is_remote,
                remote_scope,
                employment_type,
                salary_text,
                salary_min,
                salary_max,
                salary_currency,
                salary_period,
                published_at,
                source_updated_at,
                first_seen_at,
                last_seen_at,
                content_hash,
                latest_observation_hash
            )
            SELECT
                id,
                canonical_job_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                application_url,
                title,
                company_name,
                description_text,
                '[]',
                location_text,
                is_remote,
                remote_scope,
                employment_type,
                salary_text,
                salary_min,
                salary_max,
                salary_currency,
                salary_period,
                published_at,
                source_updated_at,
                first_seen_at,
                last_seen_at,
                content_hash,
                latest_observation_hash
            FROM _job_postings_source_url_required;

            INSERT INTO raw_jobs (
                id,
                job_posting_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                fetched_at,
                observation_hash,
                payload_json
            )
            SELECT
                id,
                job_posting_id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                fetched_at,
                observation_hash,
                payload_json
            FROM _raw_jobs_source_url_required;

            DROP TABLE _raw_jobs_source_url_required;
            DROP TABLE _job_postings_source_url_required;

            {schema}

            COMMIT;
            """
        )
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        if foreign_keys_enabled:
            connection.execute("PRAGMA foreign_keys = ON")


def _requires_source_tags_migration(connection: sqlite3.Connection) -> bool:
    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    return schema_version < SOURCE_TAGS_SCHEMA_VERSION


def _migrate_source_tags(connection: sqlite3.Connection) -> None:
    """Add empty source tags and rehash every legacy normalized posting."""

    try:
        connection.execute("BEGIN IMMEDIATE")
        columns = connection.execute("PRAGMA table_info(job_postings)").fetchall()
        if all(row[1] != "source_tags_json" for row in columns):
            connection.execute(
                """
                ALTER TABLE job_postings
                    ADD COLUMN source_tags_json TEXT NOT NULL DEFAULT '[]'
                    CHECK (json_valid(source_tags_json))
                    CHECK (json_type(source_tags_json) = 'array')
                """
            )

        postings = connection.execute(
            """
            SELECT
                id,
                source_provider,
                source_scope,
                external_id,
                source_url,
                application_url,
                title,
                company_name,
                description_text,
                source_tags_json,
                location_text,
                is_remote,
                remote_scope,
                employment_type,
                salary_text,
                salary_min,
                salary_max,
                salary_currency,
                salary_period,
                published_at,
                source_updated_at
            FROM job_postings
            """
        ).fetchall()
        for row in postings:
            posting = NormalizedJobPosting(
                source_provider=row["source_provider"],
                source_scope=row["source_scope"],
                external_id=row["external_id"],
                source_url=row["source_url"],
                application_url=row["application_url"],
                title=row["title"],
                company_name=row["company_name"],
                description_text=row["description_text"],
                source_tags=deserialize_source_tags(row["source_tags_json"]),
                location_text=row["location_text"],
                is_remote=row["is_remote"],
                remote_scope=row["remote_scope"],
                employment_type=row["employment_type"],
                salary_text=row["salary_text"],
                salary_min=row["salary_min"],
                salary_max=row["salary_max"],
                salary_currency=row["salary_currency"],
                salary_period=row["salary_period"],
                published_at=row["published_at"],
                source_updated_at=row["source_updated_at"],
            )
            connection.execute(
                "UPDATE job_postings SET content_hash = ? WHERE id = ?",
                (calculate_content_hash(posting), row["id"]),
            )

        connection.execute(f"PRAGMA user_version = {SOURCE_TAGS_SCHEMA_VERSION}")
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _requires_skill_intelligence_migration(
    connection: sqlite3.Connection,
) -> bool:
    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    return schema_version < SKILL_INTELLIGENCE_SCHEMA_VERSION


def _migrate_skill_intelligence(connection: sqlite3.Connection) -> None:
    """Create replaceable skill-intelligence tables without source backfill."""

    try:
        connection.executescript(
            f"""
            BEGIN IMMEDIATE;
            {load_intelligence_schema()}
            """
        )
        _validate_intelligence_schema(
            connection,
            version=SKILL_INTELLIGENCE_SCHEMA_VERSION,
        )
        connection.execute(
            f"PRAGMA user_version = {SKILL_INTELLIGENCE_SCHEMA_VERSION}"
        )
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _requires_role_intelligence_migration(
    connection: sqlite3.Connection,
) -> bool:
    return _get_schema_version(connection) < ROLE_INTELLIGENCE_SCHEMA_VERSION


def _migrate_role_intelligence(connection: sqlite3.Connection) -> None:
    """Create role-intelligence tables without backfilling existing postings."""

    try:
        connection.executescript(
            f"""
            BEGIN IMMEDIATE;
            {load_role_intelligence_schema()}
            """
        )
        _validate_role_intelligence_schema(
            connection,
            version=ROLE_INTELLIGENCE_SCHEMA_VERSION,
        )
        connection.execute(
            f"PRAGMA user_version = {ROLE_INTELLIGENCE_SCHEMA_VERSION}"
        )
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _requires_seniority_intelligence_migration(
    connection: sqlite3.Connection,
) -> bool:
    return _get_schema_version(connection) < SENIORITY_INTELLIGENCE_SCHEMA_VERSION


def _migrate_seniority_intelligence(connection: sqlite3.Connection) -> None:
    """Create seniority-intelligence tables without backfilling postings."""

    try:
        connection.executescript(
            f"""
            BEGIN IMMEDIATE;
            {load_seniority_intelligence_schema()}
            """
        )
        _validate_seniority_intelligence_schema(
            connection,
            version=SENIORITY_INTELLIGENCE_SCHEMA_VERSION,
        )
        connection.execute(
            f"PRAGMA user_version = {SENIORITY_INTELLIGENCE_SCHEMA_VERSION}"
        )
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def _requires_geography_intelligence_migration(
    connection: sqlite3.Connection,
) -> bool:
    return _get_schema_version(connection) < GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION


def _migrate_geography_intelligence(connection: sqlite3.Connection) -> None:
    """Create geography-intelligence tables without backfilling postings."""

    try:
        connection.executescript(
            f"""
            BEGIN IMMEDIATE;
            {load_geography_intelligence_schema()}
            """
        )
        _validate_geography_intelligence_schema(
            connection,
            version=GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION,
        )
        connection.execute(
            f"PRAGMA user_version = {GEOGRAPHY_INTELLIGENCE_SCHEMA_VERSION}"
        )
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
