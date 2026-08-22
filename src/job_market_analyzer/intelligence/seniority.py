"""Versioned deterministic seniority taxonomy over posting titles.

Seniority v1 is deliberately an experience-axis analyzer: intern, junior, mid,
senior, lead, staff, principal. People-management words (manager, director,
head of, VP) belong to a separate future dimension because functional titles
such as Product Manager are not people-management evidence. Generic engineering
titles without any experience signal remain Unknown.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

SENIORITY_TAXONOMY_VERSION = "1"


class SeniorityEvidenceField(StrEnum):
    """Normalized posting field that supplied seniority evidence."""

    TITLE = "title"


class SeniorityMatchKind(StrEnum):
    """How a deterministic seniority rule accepted its evidence."""

    TITLE_PATTERN = "title_pattern"


@dataclass(frozen=True, slots=True)
class SeniorityEvidence:
    """One immutable direct experience-level classification with evidence."""

    seniority_code: str
    seniority_name: str
    evidence_field: SeniorityEvidenceField
    matched_text: str
    evidence_text: str
    rule_id: str
    match_kind: SeniorityMatchKind


@dataclass(frozen=True, slots=True)
class SeniorityRule:
    """One stable regex rule for a direct experience-level phrase."""

    rule_id: str
    pattern: str
    rank: int


@dataclass(frozen=True, slots=True)
class SeniorityLevel:
    """One language-neutral seniority code with its versioned rules."""

    code: str
    name: str
    rules: tuple[SeniorityRule, ...]


def _rule(rule_id: str, pattern: str, *, rank: int) -> SeniorityRule:
    return SeniorityRule(rule_id=rule_id, pattern=pattern, rank=rank)


SENIORITY_TAXONOMY: tuple[SeniorityLevel, ...] = (
    SeniorityLevel(
        "intern",
        "Intern",
        (
            _rule("intern.named", r"\b(?:intern|internship)\b", rank=0),
        ),
    ),
    SeniorityLevel(
        "junior",
        "Junior",
        (
            _rule("junior.named", r"\b(?:junior|jr\.?)\b", rank=1),
            _rule(
                "junior.entry_level",
                r"\bentry[\s-]level\b",
                rank=1,
            ),
            _rule(
                "junior.graduate",
                r"\bgraduate[\s-]level\b",
                rank=1,
            ),
        ),
    ),
    SeniorityLevel(
        "mid",
        "Mid-level",
        (
            _rule("mid.level", r"\bmid[\s-]?level\b", rank=2),
        ),
    ),
    SeniorityLevel(
        "senior",
        "Senior",
        (
            _rule(
                "senior.named",
                r"\b(?:senior|snr)(?=\.?(?:\s|[,/]|$))|\bsr(?=\.)",
                rank=3,
            ),
        ),
    ),
    SeniorityLevel(
        "lead",
        "Lead",
        (
            _rule(
                "lead.engineering",
                r"\blead\s+(?:software\s+)?(?:engineer|developer)\b|"
                r"\blead[\s-]engineer\b|"
                r"\b(?:software\s+)?(?:engineer|developer)\s+lead\b|"
                r"\bengineering\s+lead\b",
                rank=4,
            ),
        ),
    ),
    SeniorityLevel(
        "staff",
        "Staff",
        (
            _rule(
                "staff.technical",
                r"\bstaff\s+(?:[a-z]+\s+)?"
                r"(?:engineer|developer|scientist|architect|designer)\b",
                rank=5,
            ),
        ),
    ),
    SeniorityLevel(
        "principal",
        "Principal",
        (
            _rule(
                "principal.technical",
                r"\bprincipal\s+(?:[a-z]+\s+)?"
                r"(?:engineer|developer|scientist|architect|designer)\b",
                rank=6,
            ),
        ),
    ),
)

SENIORITY_CODES: tuple[str, ...] = tuple(level.code for level in SENIORITY_TAXONOMY)

_COMPILED_RULES = tuple(
    (level, rule, re.compile(rule.pattern, re.IGNORECASE))
    for level in SENIORITY_TAXONOMY
    for rule in level.rules
)

_MAX_EVIDENCE_SNIPPET_LENGTH = 120


def extract_seniority(title: str) -> tuple[SeniorityEvidence, ...]:
    """Return at most one direct seniority evidence using the highest rank.

    Zero evidence means Unknown: the title carries no explicit experience
    signal. This is not an error and not a missing analysis.
    """

    best: tuple[
        int, int, SeniorityLevel, SeniorityRule, re.Match[str]
    ] | None = None
    for level, rule, pattern in _COMPILED_RULES:
        for match in pattern.finditer(title):
            candidate = (rule.rank, match.start(), level, rule, match)
            if best is None or (candidate[0], -candidate[1]) > (
                best[0],
                -best[1],
            ):
                best = candidate

    if best is None:
        return ()

    rank, start, level, rule, match = best
    del rank
    matched_text = match.group(0)
    return (
        SeniorityEvidence(
            seniority_code=level.code,
            seniority_name=level.name,
            evidence_field=SeniorityEvidenceField.TITLE,
            matched_text=_collapse_whitespace(matched_text),
            evidence_text=_evidence_snippet(title, start, start + len(matched_text)),
            rule_id=rule.rule_id,
            match_kind=SeniorityMatchKind.TITLE_PATTERN,
        ),
    )


def _evidence_snippet(text: str, start: int, end: int) -> str:
    max_context = 55
    left = max(0, start - max_context)
    right = min(len(text), end + max_context)

    if left > 0:
        whitespace = next(
            (index for index in range(left, start) if text[index].isspace()),
            None,
        )
        if whitespace is not None:
            left = whitespace + 1
    if right < len(text):
        whitespace = next(
            (index for index in range(right - 1, end - 1, -1) if text[index].isspace()),
            None,
        )
        if whitespace is not None:
            right = whitespace

    snippet = _collapse_whitespace(text[left:right])
    if left > 0:
        snippet = f"…{snippet}"
    if right < len(text):
        snippet = f"{snippet}…"
    if len(snippet) > _MAX_EVIDENCE_SNIPPET_LENGTH:
        snippet = f"{snippet[: _MAX_EVIDENCE_SNIPPET_LENGTH - 1].rstrip()}…"
    return snippet


def _collapse_whitespace(value: str) -> str:
    collapsed = " ".join(value.split())
    return "".join(
        character if character.isprintable() else "\ufffd" for character in collapsed
    )
