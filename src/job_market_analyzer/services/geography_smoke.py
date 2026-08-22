"""Bounded one-shot geography intelligence over current durable postings."""

from dataclasses import dataclass

from job_market_analyzer.intelligence.repository import (
    GeographyIntelligenceRepository,
)
from job_market_analyzer.services.geography_analysis import analyze_job_geography
from job_market_analyzer.storage.repository import JobPostingReader


@dataclass(frozen=True, slots=True)
class GeographyCount:
    """Distinct-posting count for one geography term in the scope."""

    code: str
    name: str
    dimension: str
    postings: int


@dataclass(frozen=True, slots=True)
class GeographySmokeSummary:
    """Aggregate result of one bounded manual geography execution."""

    postings_considered: int
    new_analysis_runs: int
    existing_analysis_runs_reused: int
    evidence_created: int
    classified_postings: int
    unknown_postings: int
    term_counts: tuple[GeographyCount, ...]


def run_geography_smoke(
    posting_reader: JobPostingReader,
    intelligence_repository: GeographyIntelligenceRepository,
    *,
    limit: int,
    sample_limit: int = 0,
) -> GeographySmokeSummary:
    """Analyze one deterministic current-posting scope without swallowing errors."""

    if limit < 1:
        raise ValueError("limit must be greater than zero")
    if sample_limit < 0:
        raise ValueError("sample_limit must not be negative")

    postings = posting_reader.list_job_postings(limit=limit)
    new_runs = 0
    reused_runs = 0
    evidence_created = 0
    classified_postings = 0
    unknown_postings = 0
    term_counts: dict[str, int] = {}
    term_meta: dict[str, tuple[str, str]] = {}

    for posting in postings:
        result = analyze_job_geography(posting, intelligence_repository)
        if result.analysis_created:
            new_runs += 1
        else:
            reused_runs += 1
        evidence_created += result.evidence_created

        evidence = intelligence_repository.get_geography_evidence(
            result.analysis_run_id
        )
        if evidence:
            classified_postings += 1
        else:
            unknown_postings += 1

        for item in evidence:
            existing = term_meta.setdefault(
                item.geography_code, (item.geography_name, item.dimension)
            )
            if existing != (item.geography_name, item.dimension):
                raise ValueError(
                    "conflicting metadata for geography code "
                    f"{item.geography_code!r}"
                )
            term_counts[item.geography_code] = (
                term_counts.get(item.geography_code, 0) + 1
            )

    terms = tuple(
        GeographyCount(code, term_meta[code][0], term_meta[code][1], count)
        for code, count in sorted(
            term_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    return GeographySmokeSummary(
        postings_considered=len(postings),
        new_analysis_runs=new_runs,
        existing_analysis_runs_reused=reused_runs,
        evidence_created=evidence_created,
        classified_postings=classified_postings,
        unknown_postings=unknown_postings,
        term_counts=terms,
    )
