"""Storage-independent contracts for replaceable derived intelligence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from job_market_analyzer.intelligence.models import SkillEvidence
from job_market_analyzer.intelligence.roles import RoleEvidence

SKILL_ANALYZER_KIND = "skills"
ROLE_ANALYZER_KIND = "roles"


@dataclass(frozen=True, slots=True)
class SkillAnalysisKey:
    """Identity of one reproducible skill-analysis execution."""

    job_posting_id: UUID
    analyzer_kind: str
    taxonomy_version: str
    extractor_version: str
    input_hash: str

    def __post_init__(self) -> None:
        """Reject non-skill analyzer identities at the skill boundary."""

        if self.analyzer_kind != SKILL_ANALYZER_KIND:
            raise ValueError(
                f"SkillAnalysisKey requires analyzer_kind={SKILL_ANALYZER_KIND!r}"
            )


@dataclass(frozen=True, slots=True)
class SkillAnalysisPersistResult:
    """Result of atomically persisting one skill-analysis execution."""

    analysis_run_id: UUID
    analysis_created: bool
    evidence_created: int


class SkillIntelligenceRepository(Protocol):
    """Persistence boundary used by deterministic skill-analysis services."""

    def find_analysis_run_id(self, key: SkillAnalysisKey) -> UUID | None:
        """Return the identical persisted run, if one already exists."""

        ...

    def persist_skill_analysis(
        self,
        key: SkillAnalysisKey,
        evidence: tuple[SkillEvidence, ...],
        *,
        created_at: datetime,
    ) -> SkillAnalysisPersistResult:
        """Persist one run and all evidence atomically and idempotently."""

        ...

    def get_skill_evidence(
        self,
        analysis_run_id: UUID,
    ) -> tuple[SkillEvidence, ...]:
        """Read the deterministic evidence stored for one analysis run."""

        ...


@dataclass(frozen=True, slots=True)
class RoleAnalysisKey:
    """Identity of one reproducible role-analysis execution."""

    job_posting_id: UUID
    analyzer_kind: str
    taxonomy_version: str
    extractor_version: str
    input_hash: str

    def __post_init__(self) -> None:
        """Reject non-role analyzer identities at the role boundary."""

        if self.analyzer_kind != ROLE_ANALYZER_KIND:
            raise ValueError(
                f"RoleAnalysisKey requires analyzer_kind={ROLE_ANALYZER_KIND!r}"
            )


@dataclass(frozen=True, slots=True)
class RoleAnalysisPersistResult:
    """Result of atomically persisting one role-analysis execution."""

    analysis_run_id: UUID
    analysis_created: bool
    evidence_created: int


class RoleIntelligenceRepository(Protocol):
    """Persistence boundary used by deterministic role-analysis services."""

    def find_analysis_run_id(self, key: RoleAnalysisKey) -> UUID | None:
        """Return the identical persisted run, if one already exists."""

        ...

    def persist_role_analysis(
        self,
        key: RoleAnalysisKey,
        evidence: tuple[RoleEvidence, ...],
        *,
        created_at: datetime,
    ) -> RoleAnalysisPersistResult:
        """Persist one run and all role evidence atomically and idempotently."""

        ...

    def get_role_evidence(
        self,
        analysis_run_id: UUID,
    ) -> tuple[RoleEvidence, ...]:
        """Read the deterministic role evidence stored for one analysis run."""

        ...
