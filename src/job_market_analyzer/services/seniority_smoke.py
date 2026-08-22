"""Bounded one-shot seniority intelligence over current durable postings."""

from dataclasses import dataclass

from job_market_analyzer.intelligence.repository import (
    SeniorityIntelligenceRepository,
)
from job_market_analyzer.services.seniority_analysis import analyze_job_seniority
from job_market_analyzer.storage.repository import JobPostingReader


@dataclass(frozen=True, slots=True)
class SeniorityCount:
    """Distinct-posting count for one seniority level in the scope."""

    code: str
    name: str
    postings: int


@dataclass(frozen=True, slots=True)
class SeniorityEvidenceSample:
    """Safe, bounded seniority evidence preview for one posting."""

    seniority_code: str
    seniority_name: str
    matched_text: str
    job_title: str
    company_name: str | None


@dataclass(frozen=True, slots=True)
class SenioritySmokeSummary:
    """Aggregate result of one bounded manual seniority execution."""

    postings_considered: int
    new_analysis_runs: int
    existing_analysis_runs_reused: int
    evidence_created: int
    classified_postings: int
    unknown_postings: int
    level_counts: tuple[SeniorityCount, ...]
    evidence_samples: tuple[SeniorityEvidenceSample, ...]
    unknown_samples: tuple[tuple[str, str | None], ...]


def run_seniority_smoke(
    posting_reader: JobPostingReader,
    intelligence_repository: SeniorityIntelligenceRepository,
    *,
    limit: int,
    sample_limit: int = 10,
) -> SenioritySmokeSummary:
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
    level_counts: dict[str, int] = {}
    level_names: dict[str, str] = {}
    evidence_samples: list[SeniorityEvidenceSample] = []
    unknown_samples: list[tuple[str, str | None]] = []

    for posting in postings:
        result = analyze_job_seniority(posting, intelligence_repository)
        if result.analysis_created:
            new_runs += 1
        else:
            reused_runs += 1
        evidence_created += result.evidence_created

        evidence = intelligence_repository.get_seniority_evidence(
            result.analysis_run_id
        )
        if evidence:
            classified_postings += 1
        else:
            unknown_postings += 1
            if len(unknown_samples) < sample_limit:
                unknown_samples.append((posting.title, posting.company_name))

        for item in evidence:
            existing_name = level_names.setdefault(
                item.seniority_code, item.seniority_name
            )
            if existing_name != item.seniority_name:
                raise ValueError(
                    "conflicting display names for seniority code "
                    f"{item.seniority_code!r}"
                )
            level_counts[item.seniority_code] = (
                level_counts.get(item.seniority_code, 0) + 1
            )
            if len(evidence_samples) < sample_limit:
                evidence_samples.append(
                    SeniorityEvidenceSample(
                        seniority_code=item.seniority_code,
                        seniority_name=item.seniority_name,
                        matched_text=item.matched_text,
                        job_title=posting.title,
                        company_name=posting.company_name,
                    )
                )

    levels = tuple(
        SeniorityCount(code, level_names[code], count)
        for code, count in sorted(
            level_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    return SenioritySmokeSummary(
        postings_considered=len(postings),
        new_analysis_runs=new_runs,
        existing_analysis_runs_reused=reused_runs,
        evidence_created=evidence_created,
        classified_postings=classified_postings,
        unknown_postings=unknown_postings,
        level_counts=levels,
        evidence_samples=tuple(evidence_samples),
        unknown_samples=tuple(unknown_samples),
    )
