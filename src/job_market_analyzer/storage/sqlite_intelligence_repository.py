"""SQLite persistence for versioned, replaceable skill intelligence."""

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
    SkillAnalysisKey,
    SkillAnalysisPersistResult,
)
from job_market_analyzer.storage.serialization import serialize_utc_datetime


class SQLiteSkillIntelligenceRepository:
    """Persist skill-analysis runs using one caller-owned SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        if connection.row_factory is not sqlite3.Row:
            raise ValueError(
                "SQLiteSkillIntelligenceRepository requires connection.row_factory "
                "to be sqlite3.Row; create the connection with connect_database()"
            )

        self._connection = connection

    def find_analysis_run_id(self, key: SkillAnalysisKey) -> UUID | None:
        """Return an identical run ID without changing database state."""

        row = self._connection.execute(
            """
            SELECT id
            FROM analysis_runs
            WHERE job_posting_id = ?
              AND analyzer_kind = ?
              AND taxonomy_version = ?
              AND extractor_version = ?
              AND input_hash = ?
            """,
            self._key_values(key),
        ).fetchone()
        return None if row is None else UUID(row["id"])

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

        created_at_value = serialize_utc_datetime(created_at)
        candidate_run_id = uuid4()
        self._connection.execute("BEGIN IMMEDIATE")

        try:
            cursor = self._connection.execute(
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
                (str(candidate_run_id), *self._key_values(key), created_at_value),
            )

            if cursor.rowcount == 0:
                existing_run_id = self.find_analysis_run_id(key)
                if existing_run_id is None:
                    raise RuntimeError("analysis run conflict did not resolve to a row")
                result = SkillAnalysisPersistResult(
                    analysis_run_id=existing_run_id,
                    analysis_created=False,
                    evidence_created=0,
                )
            else:
                self._persist_evidence(candidate_run_id, evidence)
                result = SkillAnalysisPersistResult(
                    analysis_run_id=candidate_run_id,
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

    @staticmethod
    def _key_values(key: SkillAnalysisKey) -> tuple[str, str, str, str, str]:
        return (
            str(key.job_posting_id),
            key.analyzer_kind,
            key.taxonomy_version,
            key.extractor_version,
            key.input_hash,
        )
