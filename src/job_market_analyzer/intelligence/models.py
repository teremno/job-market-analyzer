"""Immutable result models for deterministic job intelligence."""

from dataclasses import dataclass
from enum import StrEnum


class EvidenceField(StrEnum):
    """Normalized posting field that supplied the evidence."""

    TITLE = "title"
    DESCRIPTION = "description"
    TAG = "tag"


class MatchKind(StrEnum):
    """How an analyzer rule accepted the matched alias."""

    EXACT_ALIAS = "exact_alias"
    CONTEXTUAL = "contextual"


class MentionKind(StrEnum):
    """What the evidence claims about a skill mention."""

    MENTIONED = "mentioned"


@dataclass(frozen=True, slots=True)
class SkillEvidence:
    """One deterministic, source-field-specific canonical skill mention."""

    skill_code: str
    skill_name: str
    evidence_field: EvidenceField
    matched_alias: str
    evidence_text: str
    rule_id: str
    match_kind: MatchKind
    mention_kind: MentionKind = MentionKind.MENTIONED
