import sqlite3
from importlib import resources
from pathlib import Path

DatabasePath = str | Path


def load_schema() -> str:
    """Load the packaged SQLite schema."""

    schema_file = resources.files("job_market_analyzer.storage").joinpath(
        "schema.sql"
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


def initialize_database(
    connection: sqlite3.Connection,
) -> None:
    """Create the schema and apply small backward-compatible MVP migrations."""

    if connection.in_transaction:
        raise RuntimeError(
            "initialize_database must be called outside an active transaction"
        )

    try:
        connection.executescript(
            f"BEGIN IMMEDIATE;\n{load_schema()}\nCOMMIT;"
        )
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

    if _requires_nullable_source_url_migration(connection):
        _migrate_nullable_source_urls(connection)


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
