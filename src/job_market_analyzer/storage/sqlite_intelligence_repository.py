"""SQLite persistence for versioned, replaceable derived intelligence."""

import sqlite3
from datetime import datetime
from uuid import UUID, uuid4

from job_market_analyzer.intelligence.models import (
    EvidenceField,
    MatchKind,
    MentionKind,
    SkillEvidence,
)
from job_market_analyzer.intelligence.repository import (
    GeographyAnalysisKey,
    GeographyAnalysisPersistResult,
    RoleAnalysisKey,
    RoleAnalysisPersistResult,
    SeniorityAnalysisKey,
    SeniorityAnalysisPersistResult,
    SkillAnalysisKey,
    SkillAnalysisPersistResult,
)
from job_market_analyzer.intelligence.roles import (
    RoleEvidence,
    RoleEvidenceField,
    RoleMatchKind,
)
from job_market_analyzer.intelligence.geography import (
    GEOGRAPHY_TERMS,
    GeographyEvidence,
    GeographyEvidenceField,
    GeographyMatchKind,
)
from job_market_analyzer.intelligence.seniority import (
    SeniorityEvidence,
    SeniorityEvidenceField,
    SeniorityMatchKind,
)
from job_market_analyzer.storage.serialization import serialize_utc_datetime

AnalysisKey = (
    SkillAnalysisKey | RoleAnalysisKey | SeniorityAnalysisKey | GeographyAnalysisKey
)

_GEOGRAPHY_DIMENSIONS = {
    term.code: term.dimension for term in GEOGRAPHY_TERMS
}


def _validate_connection(connection: sqlite3.Connection, repository_name: str) -> None:
    if connection.row_factory is not sqlite3.Row:
        raise ValueError(
            f"{repository_name} requires connection.row_factory to be sqlite3.Row; "
            "create the connection with connect_database()"
        )


def _key_values(key: AnalysisKey) -> tuple[str, str, str, str, str]:
    return (
        str(key.job_posting_id),
        key.analyzer_kind,
        key.taxonomy_version,
        key.extractor_version,
        key.input_hash,
    )


def _find_analysis_run_id(
    connection: sqlite3.Connection,
    key: AnalysisKey,
) -> UUID | None:
    row = connection.execute(
        """
        SELECT id
        FROM analysis_runs
        WHERE job_posting_id = ?
          AND analyzer_kind = ?
          AND taxonomy_version = ?
          AND extractor_version = ?
          AND input_hash = ?
        """,
        _key_values(key),
    ).fetchone()
    return None if row is None else UUID(row["id"])


def _insert_analysis_run(
    connection: sqlite3.Connection,
    key: AnalysisKey,
    *,
    created_at: datetime,
) -> tuple[UUID, bool]:
    candidate_run_id = uuid4()
    cursor = connection.execute(
        """
        INSERT INTO analysis_runs (
            id,
            job_posting_id,
            analyzer_kind,
            taxonomy_version,
            extractor_version,
            input_hash,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (
            job_posting_id,
            analyzer_kind,
            taxonomy_version,
            extractor_version,
            input_hash
        ) DO NOTHING
        """,
        (
            str(candidate_run_id),
            *_key_values(key),
            serialize_utc_datetime(created_at),
        ),
    )
    if cursor.rowcount != 0:
        return candidate_run_id, True

    existing_run_id = _find_analysis_run_id(connection, key)
    if existing_run_id is None:
        raise RuntimeError("analysis run conflict did not resolve to a row")
    return existing_run_id, False


class SQLiteSkillIntelligenceRepository:
    """Persist skill-analysis runs using one caller-owned SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        _validate_connection(connection, type(self).__name__)
        self._connection = connection

    def find_analysis_run_id(self, key: SkillAnalysisKey) -> UUID | None:
        """Return an identical run ID without changing database state."""

        return _find_analysis_run_id(self._connection, key)

    def persist_skill_analysis(
        self,
        key: SkillAnalysisKey,
        evidence: tuple[SkillEvidence, ...],
        *,
        created_at: datetime,
    ) -> SkillAnalysisPersistResult:
        """Persist a run and its evidence in one all-or-nothing transaction."""

        if self._connection.in_transaction:
            raise RuntimeError(
                "persist_skill_analysis requires a connection without an active transaction"
            )

        self._connection.execute("BEGIN IMMEDIATE")

        try:
            analysis_run_id, analysis_created = _insert_analysis_run(
                self._connection,
                key,
                created_at=created_at,
            )
            if not analysis_created:
                result = SkillAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=False,
                    evidence_created=0,
                )
            else:
                self._persist_evidence(analysis_run_id, evidence)
                result = SkillAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=True,
                    evidence_created=len(evidence),
                )

            self._connection.commit()
        except BaseException:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise

        return result

    def get_skill_evidence(
        self,
        analysis_run_id: UUID,
    ) -> tuple[SkillEvidence, ...]:
        """Reconstruct stored direct-mention evidence for one run."""

        rows = self._connection.execute(
            """
            SELECT
                job_skills.skill_code,
                job_skills.skill_name,
                job_skills.evidence_field,
                job_skills.matched_alias,
                job_skills.evidence_text,
                job_skills.rule_id,
                job_skills.match_kind,
                job_skills.mention_kind
            FROM job_skills
            WHERE job_skills.analysis_run_id = ?
            ORDER BY
                job_skills.skill_code,
                CASE job_skills.evidence_field
                    WHEN 'title' THEN 0
                    WHEN 'description' THEN 1
                    ELSE 2
                END,
                job_skills.rule_id
            """,
            (str(analysis_run_id),),
        ).fetchall()
        return tuple(
            SkillEvidence(
                skill_code=row["skill_code"],
                skill_name=row["skill_name"],
                evidence_field=EvidenceField(row["evidence_field"]),
                matched_alias=row["matched_alias"],
                evidence_text=row["evidence_text"],
                rule_id=row["rule_id"],
                match_kind=MatchKind(row["match_kind"]),
                mention_kind=MentionKind(row["mention_kind"]),
            )
            for row in rows
        )

    def _persist_evidence(
        self,
        analysis_run_id: UUID,
        evidence: tuple[SkillEvidence, ...],
    ) -> None:
        skill_names: dict[str, str] = {}
        for item in evidence:
            previous_name = skill_names.setdefault(item.skill_code, item.skill_name)
            if previous_name != item.skill_name:
                raise ValueError(
                    f"conflicting display names for skill code {item.skill_code!r}"
                )

        self._connection.executemany(
            """
            INSERT INTO skills (code, display_name)
            VALUES (?, ?)
            ON CONFLICT (code) DO NOTHING
            """,
            skill_names.items(),
        )
        self._connection.executemany(
            """
            INSERT INTO job_skills (
                analysis_run_id,
                skill_code,
                skill_name,
                evidence_field,
                matched_alias,
                evidence_text,
                rule_id,
                match_kind,
                mention_kind
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    str(analysis_run_id),
                    item.skill_code,
                    item.skill_name,
                    item.evidence_field.value,
                    item.matched_alias,
                    item.evidence_text,
                    item.rule_id,
                    item.match_kind.value,
                    item.mention_kind.value,
                )
                for item in evidence
            ),
        )


class SQLiteRoleIntelligenceRepository:
    """Persist role-analysis runs using one caller-owned SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        _validate_connection(connection, type(self).__name__)
        self._connection = connection

    def find_analysis_run_id(self, key: RoleAnalysisKey) -> UUID | None:
        """Return an identical run ID without changing database state."""

        return _find_analysis_run_id(self._connection, key)

    def persist_role_analysis(
        self,
        key: RoleAnalysisKey,
        evidence: tuple[RoleEvidence, ...],
        *,
        created_at: datetime,
    ) -> RoleAnalysisPersistResult:
        """Persist a role run and its evidence in one transaction."""

        if self._connection.in_transaction:
            raise RuntimeError(
                "persist_role_analysis requires a connection without an active transaction"
            )

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            analysis_run_id, analysis_created = _insert_analysis_run(
                self._connection,
                key,
                created_at=created_at,
            )
            if not analysis_created:
                result = RoleAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=False,
                    evidence_created=0,
                )
            else:
                self._persist_evidence(analysis_run_id, evidence)
                result = RoleAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=True,
                    evidence_created=len(evidence),
                )
            self._connection.commit()
        except BaseException:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        return result

    def get_role_evidence(
        self,
        analysis_run_id: UUID,
    ) -> tuple[RoleEvidence, ...]:
        """Reconstruct stored role evidence using historical label snapshots."""

        rows = self._connection.execute(
            """
            SELECT
                role_code,
                role_name,
                evidence_field,
                matched_text,
                evidence_text,
                rule_id,
                match_kind
            FROM job_roles
            WHERE analysis_run_id = ?
            ORDER BY role_code, rule_id
            """,
            (str(analysis_run_id),),
        ).fetchall()
        return tuple(
            RoleEvidence(
                role_code=row["role_code"],
                role_name=row["role_name"],
                evidence_field=RoleEvidenceField(row["evidence_field"]),
                matched_text=row["matched_text"],
                evidence_text=row["evidence_text"],
                rule_id=row["rule_id"],
                match_kind=RoleMatchKind(row["match_kind"]),
            )
            for row in rows
        )

    def _persist_evidence(
        self,
        analysis_run_id: UUID,
        evidence: tuple[RoleEvidence, ...],
    ) -> None:
        role_names: dict[str, str] = {}
        for item in evidence:
            previous_name = role_names.setdefault(item.role_code, item.role_name)
            if previous_name != item.role_name:
                raise ValueError(
                    f"conflicting display names for role code {item.role_code!r}"
                )

        self._connection.executemany(
            """
            INSERT INTO roles (code, display_name)
            VALUES (?, ?)
            ON CONFLICT (code) DO NOTHING
            """,
            role_names.items(),
        )
        self._connection.executemany(
            """
            INSERT INTO job_roles (
                analysis_run_id,
                role_code,
                role_name,
                evidence_field,
                matched_text,
                evidence_text,
                rule_id,
                match_kind
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    str(analysis_run_id),
                    item.role_code,
                    item.role_name,
                    item.evidence_field.value,
                    item.matched_text,
                    item.evidence_text,
                    item.rule_id,
                    item.match_kind.value,
                )
                for item in evidence
            ),
        )


class SQLiteSeniorityIntelligenceRepository:
    """Persist seniority-analysis runs using one caller-owned connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        _validate_connection(connection, type(self).__name__)
        self._connection = connection

    def find_analysis_run_id(self, key: SeniorityAnalysisKey) -> UUID | None:
        """Return an identical run ID without changing database state."""

        return _find_analysis_run_id(self._connection, key)

    def persist_seniority_analysis(
        self,
        key: SeniorityAnalysisKey,
        evidence: tuple[SeniorityEvidence, ...],
        *,
        created_at: datetime,
    ) -> SeniorityAnalysisPersistResult:
        """Persist a seniority run and its evidence in one transaction."""

        if self._connection.in_transaction:
            raise RuntimeError(
                "persist_seniority_analysis requires a connection "
                "without an active transaction"
            )

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            analysis_run_id, analysis_created = _insert_analysis_run(
                self._connection,
                key,
                created_at=created_at,
            )
            if not analysis_created:
                result = SeniorityAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=False,
                    evidence_created=0,
                )
            else:
                self._persist_evidence(analysis_run_id, evidence)
                result = SeniorityAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=True,
                    evidence_created=len(evidence),
                )
            self._connection.commit()
        except BaseException:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        return result

    def get_seniority_evidence(
        self,
        analysis_run_id: UUID,
    ) -> tuple[SeniorityEvidence, ...]:
        """Reconstruct stored seniority evidence using label snapshots."""

        rows = self._connection.execute(
            """
            SELECT
                seniority_code,
                seniority_name,
                evidence_field,
                matched_text,
                evidence_text,
                rule_id,
                match_kind
            FROM job_seniority
            WHERE analysis_run_id = ?
            ORDER BY seniority_code, rule_id
            """,
            (str(analysis_run_id),),
        ).fetchall()
        return tuple(
            SeniorityEvidence(
                seniority_code=row["seniority_code"],
                seniority_name=row["seniority_name"],
                evidence_field=SeniorityEvidenceField(row["evidence_field"]),
                matched_text=row["matched_text"],
                evidence_text=row["evidence_text"],
                rule_id=row["rule_id"],
                match_kind=SeniorityMatchKind(row["match_kind"]),
            )
            for row in rows
        )

    def _persist_evidence(
        self,
        analysis_run_id: UUID,
        evidence: tuple[SeniorityEvidence, ...],
    ) -> None:
        level_names: dict[str, str] = {}
        for item in evidence:
            previous_name = level_names.setdefault(
                item.seniority_code, item.seniority_name
            )
            if previous_name != item.seniority_name:
                raise ValueError(
                    "conflicting display names for seniority code "
                    f"{item.seniority_code!r}"
                )

        self._connection.executemany(
            """
            INSERT INTO seniority_levels (code, display_name)
            VALUES (?, ?)
            ON CONFLICT (code) DO NOTHING
            """,
            level_names.items(),
        )
        self._connection.executemany(
            """
            INSERT INTO job_seniority (
                analysis_run_id,
                seniority_code,
                seniority_name,
                evidence_field,
                matched_text,
                evidence_text,
                rule_id,
                match_kind
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    str(analysis_run_id),
                    item.seniority_code,
                    item.seniority_name,
                    item.evidence_field.value,
                    item.matched_text,
                    item.evidence_text,
                    item.rule_id,
                    item.match_kind.value,
                )
                for item in evidence
            ),
        )


class SQLiteGeographyIntelligenceRepository:
    """Persist geography-analysis runs using one caller-owned connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        _validate_connection(connection, type(self).__name__)
        self._connection = connection

    def find_analysis_run_id(self, key: GeographyAnalysisKey) -> UUID | None:
        """Return an identical run ID without changing database state."""

        return _find_analysis_run_id(self._connection, key)

    def persist_geography_analysis(
        self,
        key: GeographyAnalysisKey,
        evidence: tuple[GeographyEvidence, ...],
        *,
        created_at: datetime,
    ) -> GeographyAnalysisPersistResult:
        """Persist a geography run and its evidence in one transaction."""

        if self._connection.in_transaction:
            raise RuntimeError(
                "persist_geography_analysis requires a connection "
                "without an active transaction"
            )

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            analysis_run_id, analysis_created = _insert_analysis_run(
                self._connection,
                key,
                created_at=created_at,
            )
            if not analysis_created:
                result = GeographyAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=False,
                    evidence_created=0,
                )
            else:
                self._persist_evidence(analysis_run_id, evidence)
                result = GeographyAnalysisPersistResult(
                    analysis_run_id=analysis_run_id,
                    analysis_created=True,
                    evidence_created=len(evidence),
                )
            self._connection.commit()
        except BaseException:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        return result

    def get_geography_evidence(
        self,
        analysis_run_id: UUID,
    ) -> tuple[GeographyEvidence, ...]:
        """Reconstruct stored geography evidence using label snapshots."""

        rows = self._connection.execute(
            """
            SELECT
                geography_code,
                geography_name,
                dimension,
                evidence_field,
                matched_text,
                evidence_text,
                rule_id,
                match_kind
            FROM job_geography
            WHERE analysis_run_id = ?
            ORDER BY geography_code, rule_id
            """,
            (str(analysis_run_id),),
        ).fetchall()
        return tuple(
            GeographyEvidence(
                geography_code=row["geography_code"],
                geography_name=row["geography_name"],
                dimension=row["dimension"],
                evidence_field=GeographyEvidenceField(row["evidence_field"]),
                matched_text=row["matched_text"],
                evidence_text=row["evidence_text"],
                rule_id=row["rule_id"],
                match_kind=GeographyMatchKind(row["match_kind"]),
            )
            for row in rows
        )

    def _persist_evidence(
        self,
        analysis_run_id: UUID,
        evidence: tuple[GeographyEvidence, ...],
    ) -> None:
        term_names: dict[str, str] = {}
        for item in evidence:
            previous_name = term_names.setdefault(
                item.geography_code, item.geography_name
            )
            if previous_name != item.geography_name:
                raise ValueError(
                    "conflicting display names for geography code "
                    f"{item.geography_code!r}"
                )

        self._connection.executemany(
            """
            INSERT INTO geography_terms (code, display_name, dimension)
            VALUES (?, ?, ?)
            ON CONFLICT (code) DO NOTHING
            """,
            (
                (
                    code,
                    name,
                    _GEOGRAPHY_DIMENSIONS[code],
                )
                for code, name in term_names.items()
            ),
        )
        self._connection.executemany(
            """
            INSERT INTO job_geography (
                analysis_run_id,
                geography_code,
                geography_name,
                dimension,
                evidence_field,
                matched_text,
                evidence_text,
                rule_id,
                match_kind
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    str(analysis_run_id),
                    item.geography_code,
                    item.geography_name,
                    item.dimension,
                    item.evidence_field.value,
                    item.matched_text,
                    item.evidence_text,
                    item.rule_id,
                    item.match_kind.value,
                )
                for item in evidence
            ),
        )
