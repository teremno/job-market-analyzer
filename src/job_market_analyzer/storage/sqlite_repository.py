"""Concrete SQLite persistence for collected job observations."""

import sqlite3
from uuid import UUID, uuid4

from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.storage.repository import (
    PersistResult,
    SourceIdentityMismatchError,
)
from job_market_analyzer.storage.serialization import (
    SQLiteValue,
    calculate_content_hash,
    calculate_observation_hash,
    serialize_normalized_posting,
    serialize_raw_payload,
    serialize_utc_datetime,
)


class SQLiteJobRepository:
    """
    Persist normalized job observations using one caller-owned connection.

    The connection must use ``sqlite3.Row`` as its row factory. Use
    ``connect_database()`` to create a correctly configured connection.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        if connection.row_factory is not sqlite3.Row:
            raise ValueError(
                "SQLiteJobRepository requires connection.row_factory to be "
                "sqlite3.Row; create the connection with connect_database()"
            )

        self._connection = connection

    def persist_observation(
        self,
        raw_job: RawJob,
        posting: NormalizedJobPosting,
    ) -> PersistResult:
        """Persist one observation atomically with same-source upsert semantics."""

        self._validate_source_identity(raw_job, posting)

        if self._connection.in_transaction:
            raise RuntimeError(
                "persist_observation requires a connection without an active transaction"
            )

        payload_json = serialize_raw_payload(raw_job.payload)
        observation_hash = calculate_observation_hash(raw_job)
        posting_values = serialize_normalized_posting(posting)
        content_hash = calculate_content_hash(posting)
        fetched_at = serialize_utc_datetime(raw_job.fetched_at)
        raw_values: dict[str, SQLiteValue] = {
            "external_id": raw_job.external_id,
            "fetched_at": fetched_at,
            "id": str(raw_job.id),
            "observation_hash": observation_hash,
            "payload_json": payload_json,
            "source_provider": raw_job.source_provider,
            "source_scope": raw_job.source_scope,
            "source_url": str(raw_job.source_url),
        }

        self._connection.execute("BEGIN IMMEDIATE")

        try:
            result = self._persist_in_transaction(
                raw_job_id=raw_job.id,
                raw_values=raw_values,
                posting_values=posting_values,
                observation_hash=observation_hash,
                content_hash=content_hash,
                fetched_at=fetched_at,
            )
            self._connection.commit()
        except BaseException:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise

        return result

    def _persist_in_transaction(
        self,
        *,
        raw_job_id: UUID,
        raw_values: dict[str, SQLiteValue],
        posting_values: dict[str, SQLiteValue],
        observation_hash: str,
        content_hash: str,
        fetched_at: str,
    ) -> PersistResult:
        existing = self._connection.execute(
            """
            SELECT
                id,
                canonical_job_id,
                first_seen_at,
                last_seen_at,
                latest_observation_hash
            FROM job_postings
            WHERE source_provider = ?
              AND source_scope = ?
              AND external_id = ?
            """,
            (
                posting_values["source_provider"],
                posting_values["source_scope"],
                posting_values["external_id"],
            ),
        ).fetchone()

        if existing is None:
            return self._create_new_posting(
                raw_job_id=raw_job_id,
                raw_values=raw_values,
                posting_values=posting_values,
                observation_hash=observation_hash,
                content_hash=content_hash,
                fetched_at=fetched_at,
            )

        return self._update_existing_posting(
            existing=existing,
            raw_job_id=raw_job_id,
            raw_values=raw_values,
            posting_values=posting_values,
            observation_hash=observation_hash,
            content_hash=content_hash,
            fetched_at=fetched_at,
        )

    def _create_new_posting(
        self,
        *,
        raw_job_id: UUID,
        raw_values: dict[str, SQLiteValue],
        posting_values: dict[str, SQLiteValue],
        observation_hash: str,
        content_hash: str,
        fetched_at: str,
    ) -> PersistResult:
        canonical_job_id = uuid4()
        job_posting_id = uuid4()

        self._connection.execute(
            """
            INSERT INTO canonical_jobs (id, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (str(canonical_job_id), fetched_at, fetched_at),
        )

        self._insert_job_posting(
            job_posting_id=job_posting_id,
            canonical_job_id=canonical_job_id,
            posting_values=posting_values,
            first_seen_at=fetched_at,
            last_seen_at=fetched_at,
            content_hash=content_hash,
            latest_observation_hash=observation_hash,
        )
        self._insert_raw_observation(
            raw_values=raw_values,
            job_posting_id=job_posting_id,
        )

        return PersistResult(
            canonical_job_id=canonical_job_id,
            job_posting_id=job_posting_id,
            raw_job_id=raw_job_id,
            canonical_created=True,
            posting_created=True,
            raw_observation_created=True,
        )

    def _update_existing_posting(
        self,
        *,
        existing: sqlite3.Row,
        raw_job_id: UUID,
        raw_values: dict[str, SQLiteValue],
        posting_values: dict[str, SQLiteValue],
        observation_hash: str,
        content_hash: str,
        fetched_at: str,
    ) -> PersistResult:
        job_posting_id = UUID(existing["id"])
        canonical_job_id = UUID(existing["canonical_job_id"])
        existing_last_seen = existing["last_seen_at"]
        observation_changed = observation_hash != existing["latest_observation_hash"]

        if observation_changed:
            self._insert_raw_observation(
                raw_values=raw_values,
                job_posting_id=job_posting_id,
            )

        if fetched_at >= existing_last_seen:
            self._update_current_posting_state(
                job_posting_id=job_posting_id,
                posting_values=posting_values,
                last_seen_at=fetched_at,
                content_hash=content_hash,
                latest_observation_hash=(
                    observation_hash
                    if observation_changed
                    else existing["latest_observation_hash"]
                ),
            )
        elif observation_changed:
            self._connection.execute(
                """
                UPDATE job_postings
                SET latest_observation_hash = ?
                WHERE id = ?
                """,
                (observation_hash, str(job_posting_id)),
            )

        return PersistResult(
            canonical_job_id=canonical_job_id,
            job_posting_id=job_posting_id,
            raw_job_id=raw_job_id if observation_changed else None,
            canonical_created=False,
            posting_created=False,
            raw_observation_created=observation_changed,
        )

    def _insert_job_posting(
        self,
        *,
        job_posting_id: UUID,
        canonical_job_id: UUID,
        posting_values: dict[str, SQLiteValue],
        first_seen_at: str,
        last_seen_at: str,
        content_hash: str,
        latest_observation_hash: str,
    ) -> None:
        self._connection.execute(
            """
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
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                str(job_posting_id),
                str(canonical_job_id),
                posting_values["source_provider"],
                posting_values["source_scope"],
                posting_values["external_id"],
                posting_values["source_url"],
                posting_values["application_url"],
                posting_values["title"],
                posting_values["company_name"],
                posting_values["description_text"],
                posting_values["location_text"],
                posting_values["is_remote"],
                posting_values["remote_scope"],
                posting_values["employment_type"],
                posting_values["salary_text"],
                posting_values["salary_min"],
                posting_values["salary_max"],
                posting_values["salary_currency"],
                posting_values["salary_period"],
                posting_values["published_at"],
                posting_values["source_updated_at"],
                first_seen_at,
                last_seen_at,
                content_hash,
                latest_observation_hash,
            ),
        )

    def _update_current_posting_state(
        self,
        *,
        job_posting_id: UUID,
        posting_values: dict[str, SQLiteValue],
        last_seen_at: str,
        content_hash: str,
        latest_observation_hash: str,
    ) -> None:
        self._connection.execute(
            """
            UPDATE job_postings
            SET source_url = ?,
                application_url = ?,
                title = ?,
                company_name = ?,
                description_text = ?,
                location_text = ?,
                is_remote = ?,
                remote_scope = ?,
                employment_type = ?,
                salary_text = ?,
                salary_min = ?,
                salary_max = ?,
                salary_currency = ?,
                salary_period = ?,
                published_at = ?,
                source_updated_at = ?,
                last_seen_at = ?,
                content_hash = ?,
                latest_observation_hash = ?
            WHERE id = ?
            """,
            (
                posting_values["source_url"],
                posting_values["application_url"],
                posting_values["title"],
                posting_values["company_name"],
                posting_values["description_text"],
                posting_values["location_text"],
                posting_values["is_remote"],
                posting_values["remote_scope"],
                posting_values["employment_type"],
                posting_values["salary_text"],
                posting_values["salary_min"],
                posting_values["salary_max"],
                posting_values["salary_currency"],
                posting_values["salary_period"],
                posting_values["published_at"],
                posting_values["source_updated_at"],
                last_seen_at,
                content_hash,
                latest_observation_hash,
                str(job_posting_id),
            ),
        )

    def _insert_raw_observation(
        self,
        *,
        raw_values: dict[str, SQLiteValue],
        job_posting_id: UUID,
    ) -> None:
        self._connection.execute(
            """
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                raw_values["id"],
                str(job_posting_id),
                raw_values["source_provider"],
                raw_values["source_scope"],
                raw_values["external_id"],
                raw_values["source_url"],
                raw_values["fetched_at"],
                raw_values["observation_hash"],
                raw_values["payload_json"],
            ),
        )

    @staticmethod
    def _validate_source_identity(
        raw_job: RawJob,
        posting: NormalizedJobPosting,
    ) -> None:
        raw_identity = (
            raw_job.source_provider,
            raw_job.source_scope,
            raw_job.external_id,
        )
        posting_identity = (
            posting.source_provider,
            posting.source_scope,
            posting.external_id,
        )

        if raw_identity != posting_identity:
            raise SourceIdentityMismatchError(
                "RawJob and NormalizedJobPosting source identities do not match"
            )
