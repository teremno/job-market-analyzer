"""Pure deterministic intelligence contracts and extractors."""

from job_market_analyzer.intelligence.hashing import calculate_skill_input_hash
from job_market_analyzer.intelligence.models import (
    EvidenceField,
    MatchKind,
    MentionKind,
    SkillEvidence,
)
from job_market_analyzer.intelligence.repository import (
    SKILL_ANALYZER_KIND,
    SkillAnalysisKey,
    SkillAnalysisPersistResult,
    SkillIntelligenceRepository,
)
from job_market_analyzer.intelligence.roles import (
    ROLE_CODES,
    ROLE_TAXONOMY_VERSION,
    RoleEvidence,
    RoleEvidenceField,
    RoleMatchKind,
    extract_roles,
)
from job_market_analyzer.intelligence.skills import (
    SKILL_TAXONOMY,
    SKILL_TAXONOMY_VERSION,
    SkillAlias,
    SkillDefinition,
    extract_skills,
)

__all__ = [
    "SKILL_TAXONOMY",
    "SKILL_TAXONOMY_VERSION",
    "EvidenceField",
    "MatchKind",
    "MentionKind",
    "ROLE_CODES",
    "ROLE_TAXONOMY_VERSION",
    "RoleEvidence",
    "RoleEvidenceField",
    "RoleMatchKind",
    "SkillAlias",
    "SKILL_ANALYZER_KIND",
    "SkillAnalysisKey",
    "SkillAnalysisPersistResult",
    "SkillDefinition",
    "SkillEvidence",
    "SkillIntelligenceRepository",
    "calculate_skill_input_hash",
    "extract_skills",
    "extract_roles",
]
