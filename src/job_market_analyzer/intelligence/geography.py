"""Versioned deterministic geography classification over posting inputs.

Geography v1 classifies two independent dimensions:

1. Work arrangement (at most one): ``arrangement_remote``, ``arrangement_hybrid``
   or ``arrangement_onsite``. The structured ``is_remote`` flag is authoritative
   when the source supplies one; otherwise guarded description/location phrases
   decide, with explicit full-remote phrasing beating generic mentions.
2. Region eligibility (multi-label): ``region_worldwide``, ``region_europe``,
   ``region_north_america``, ``region_latin_america`` and ``region_asia_pacific``.

The analyzer never infers a region from nothing: zero evidence on a dimension
is Unknown, not an error. Titles are intentionally not an input because job
titles almost never carry eligibility information and this keeps the input
hash stable under retitling.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

GEOGRAPHY_TAXONOMY_VERSION = "1"


class GeographyEvidenceField(StrEnum):
    """Normalized posting field that supplied geography evidence."""

    DESCRIPTION = "description"
    LOCATION = "location"
    STRUCTURED = "structured"


class GeographyMatchKind(StrEnum):
    """How a deterministic geography rule accepted its evidence."""

    TITLE_PATTERN = "title_pattern"
    DESCRIPTION_STATEMENT = "description_statement"
    NORMALIZED_FIELD = "normalized_field"


@dataclass(frozen=True, slots=True)
class GeographyEvidence:
    """One immutable direct geography classification with evidence."""

    geography_code: str
    geography_name: str
    dimension: str
    evidence_field: GeographyEvidenceField
    matched_text: str
    evidence_text: str
    rule_id: str
    match_kind: GeographyMatchKind


@dataclass(frozen=True, slots=True)
class GeographyTerm:
    """One stable geography code with its display name."""

    code: str
    name: str
    dimension: str


GEOGRAPHY_TERMS: tuple[GeographyTerm, ...] = (
    GeographyTerm("arrangement_remote", "Remote", "arrangement"),
    GeographyTerm("arrangement_hybrid", "Hybrid", "arrangement"),
    GeographyTerm("arrangement_onsite", "Onsite", "arrangement"),
    GeographyTerm("region_worldwide", "Worldwide", "region"),
    GeographyTerm("region_europe", "Europe", "region"),
    GeographyTerm("region_north_america", "North America", "region"),
    GeographyTerm("region_latin_america", "Latin America", "region"),
    GeographyTerm("region_asia_pacific", "Asia Pacific", "region"),
)

_TERM_INDEX = {term.code: term for term in GEOGRAPHY_TERMS}

# Arrangement rules are evaluated in order; first hit wins.
_ARRANGEMENT_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "geography.arrangement.full_remote",
        "arrangement_remote",
        re.compile(
            r"\b(?:100%[\s-]?remote|fully[\s-]remote|remote[-\s]first|"
            r"work(?:\s+from)?\s+(?:anywhere|home)|remote\s+position|"
            r"remote\s+role|remote\s+job|this\s+is\s+a\s+remote)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "geography.arrangement.hybrid",
        "arrangement_hybrid",
        re.compile(
            r"\bhybrid\s+(?:work(?:ing)?(?:\s+(?:model|environment|schedule|"
            r"arrangement|role|position))?|role|position|team)\b|"
            r"\bwork\s+hybrid(?:ly)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "geography.arrangement.remote_generic",
        "arrangement_remote",
        re.compile(r"\bremote\b", re.IGNORECASE),
    ),
    (
        "geography.arrangement.onsite",
        "arrangement_onsite",
        re.compile(
            r"\b(?:work(?:ing)?\s+)?on[\s-]?site\b|\boffice[\s-]based\b|"
            r"\bin[\s-]office\b",
            re.IGNORECASE,
        ),
    ),
)

_REGION_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "geography.region.worldwide",
        "region_worldwide",
        re.compile(
            r"\bworldwide\b|"
            r"\b(?:remotely\s+)?(?:work(?:ing)?\s+|from\s+)?anywhere\b"
            r"(?![^.]{0,40}\b(?:in|within|across)\s+)",
            re.IGNORECASE,
        ),
    ),
    (
        "geography.region.europe",
        "region_europe",
        re.compile(
            r"\beuropean\s+union\b|\beurope\b|\beu\b|"
            r"\bemea\b(?![^.]{0,20}\b(?:excluding))",
            re.IGNORECASE,
        ),
    ),
    (
        "geography.region.north_america",
        "region_north_america",
        re.compile(
            r"\bunited\s+states(?:\s+of\s+america)?\b|\bu\.?s\.?a?\.(?=\s|$)|"
            r"\busa\b|\busa?\s*[-/]?\s*(?:based|only|citizens?|residents?|"
            r"candidates?|persons?)\b|\bnorth\s+america\b|\bcanada\b",
            re.IGNORECASE,
        ),
    ),
    (
        "geography.region.latin_america",
        "region_latin_america",
        re.compile(
            r"\blatin\s+america\b|\blatam\b|\b(?:south|central)\s+america\b",
            re.IGNORECASE,
        ),
    ),
    (
        "geography.region.asia_pacific",
        "region_asia_pacific",
        re.compile(r"\bapac\b|\basia[\s-]?pacific\b|\basia\b", re.IGNORECASE),
    ),
)

_MAX_EVIDENCE_SNIPPET_LENGTH = 120


def extract_geography(
    description_text: str | None,
    *,
    location_text: str | None,
    is_remote: bool | None,
) -> tuple[GeographyEvidence, ...]:
    """Return direct geography evidence from normalized posting inputs."""

    arrangement = _extract_arrangement(is_remote=is_remote, text=description_text)
    regions = _extract_regions(text=description_text, location_text=location_text)
    return tuple(sorted((*arrangement, *regions), key=lambda item: item.geography_code))


def _extract_arrangement(
    *,
    is_remote: bool | None,
    text: str | None,
) -> tuple[GeographyEvidence, ...]:
    # A structured source flag is authoritative when present.
    if is_remote is not None:
        code = "arrangement_remote" if is_remote else None
        if code is None:
            return ()
        term = _TERM_INDEX[code]
        return (
            GeographyEvidence(
                geography_code=term.code,
                geography_name=term.name,
                dimension=term.dimension,
                evidence_field=GeographyEvidenceField.STRUCTURED,
                matched_text="is_remote=true",
                evidence_text="source supplied is_remote=true",
                rule_id="geography.arrangement.structured",
                match_kind=GeographyMatchKind.NORMALIZED_FIELD,
            ),
        )

    if text is None or not text.strip():
        return ()

    for rule_id, code, pattern in _ARRANGEMENT_RULES:
        match = pattern.search(text)
        if match is None:
            continue
        return (_evidence(code, rule_id, GeographyEvidenceField.DESCRIPTION, match, text),)
    return ()


def _extract_regions(
    *, text: str | None, location_text: str | None
) -> tuple[GeographyEvidence, ...]:
    evidences: list[GeographyEvidence] = []
    seen_codes: set[str] = set()

    sources: list[tuple[GeographyEvidenceField, str | None]] = [
        (GeographyEvidenceField.LOCATION, location_text),
        (GeographyEvidenceField.DESCRIPTION, text),
    ]
    for field, value in sources:
        if value is None or not value.strip():
            continue
        for rule_id, code, pattern in _REGION_RULES:
            if code in seen_codes:
                continue
            match = pattern.search(value)
            if match is None:
                continue
            seen_codes.add(code)
            evidences.append(_evidence(code, rule_id, field, match, value))
    return tuple(evidences)


def _evidence(
    code: str,
    rule_id: str,
    field: GeographyEvidenceField,
    match: re.Match[str],
    text: str,
) -> GeographyEvidence:
    term = _TERM_INDEX[code]
    match_kind = (
        GeographyMatchKind.TITLE_PATTERN
        if field is GeographyEvidenceField.LOCATION
        else GeographyMatchKind.DESCRIPTION_STATEMENT
    )
    return GeographyEvidence(
        geography_code=code,
        geography_name=term.name,
        dimension=term.dimension,
        evidence_field=field,
        matched_text=_collapse_whitespace(match.group(0)),
        evidence_text=_evidence_snippet(text, match.start(), match.end()),
        rule_id=rule_id,
        match_kind=match_kind,
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
