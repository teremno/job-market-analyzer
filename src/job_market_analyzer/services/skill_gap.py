"""Deterministic read-only skill-gap calculation over market evidence.

Skill Gap v1 answers one question honestly: for a target role, which skills
does the active market dataset mention most often, and which of those the user
does not already claim? It is a pure calculator over ``AnalyticsRepository``:
no persistence, no profiles, no AI, and no network.

Every entry is mention-level evidence ("mentioned in N of M role postings"),
never a requirement claim. Skill inputs are recognized against the canonical
taxonomy by code or display name, case-insensitively; unrecognized inputs are
reported back instead of being silently dropped or invented.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from job_market_analyzer.analytics import AnalyticsRepository, RoleDetail
from job_market_analyzer.intelligence.skills import SKILL_TAXONOMY

MAX_MARKET_SKILLS = 100


@dataclass(frozen=True, slots=True)
class MarketSkill:
    """One skill's mention evidence within the target role."""

    skill_code: str
    skill_name: str
    posting_count: int
    share_of_role_postings: float
    status: str  # "gap" | "known"


@dataclass(frozen=True, slots=True)
class SkillGapReport:
    """Full deterministic result for one role and one known-skill set."""

    role_code: str
    role_name: str
    role_posting_count: int
    known_recognized: tuple[str, ...]
    unknown_inputs: tuple[str, ...]
    gaps: tuple[MarketSkill, ...]
    matched_market_skills: tuple[MarketSkill, ...]


def _skill_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for skill in SKILL_TAXONOMY:
        for key in (skill.code.casefold(), skill.name.casefold()):
            existing = lookup.get(key)
            if existing is not None and existing != skill.code:
                raise ValueError(f"skill lookup collision on {key!r}")
            lookup[key] = skill.code
    return lookup


def compute_skill_gap(
    analytics: AnalyticsRepository,
    *,
    role_code: str,
    known_skill_inputs: Sequence[str],
) -> SkillGapReport | None:
    """Compute the gap for one role, or return None for an unknown role.

    The caller owns input hygiene; blank inputs are ignored here so CLI and
    future interfaces can pass raw lists.
    """

    detail: RoleDetail | None = analytics.get_role_detail(
        role_code,
        top_limit=MAX_MARKET_SKILLS,
    )
    if detail is None:
        return None

    lookup = _skill_lookup()
    recognized_known: set[str] = set()
    unknown_inputs: list[str] = []
    for raw_input in known_skill_inputs:
        cleaned = raw_input.strip().casefold()
        if not cleaned:
            continue
        code = lookup.get(cleaned)
        if code is None and raw_input.strip() not in unknown_inputs:
            unknown_inputs.append(raw_input.strip())
        else:
            recognized_known.add(code)

    total = max(detail.posting_count, 1)
    market: list[MarketSkill] = []
    for skill in detail.top_skills:
        share = skill.posting_count / total
        status = "known" if skill.skill_code in recognized_known else "gap"
        market.append(
            MarketSkill(
                skill_code=skill.skill_code,
                skill_name=skill.skill_name,
                posting_count=skill.posting_count,
                share_of_role_postings=share,
                status=status,
            )
        )

    gaps = tuple(item for item in market if item.status == "gap")
    matched = tuple(item for item in market if item.status == "known")
    return SkillGapReport(
        role_code=detail.role_code,
        role_name=detail.role_name,
        role_posting_count=detail.posting_count,
        known_recognized=tuple(sorted(recognized_known)),
        unknown_inputs=tuple(unknown_inputs),
        gaps=gaps,
        matched_market_skills=matched,
    )
