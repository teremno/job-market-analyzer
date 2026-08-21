"""Bounded one-shot role intelligence over current durable postings."""

from dataclasses import dataclass

from job_market_analyzer.intelligence.repository import RoleIntelligenceRepository
from job_market_analyzer.services.role_analysis import analyze_job_roles
from job_market_analyzer.storage.repository import JobPostingReader


@dataclass(frozen=True, slots=True)
class RoleCount:
    """Distinct-posting count for one canonical role in the execution scope."""

    code: str
    name: str
    postings: int


@dataclass(frozen=True, slots=True)
class RoleEvidenceSample:
    """Safe, bounded role evidence preview tied to its current posting."""

    role_code: str
    role_name: str
    evidence_field: str
    matched_text: str
    job_title: str
    company_name: str | None
    evidence_text: str


@dataclass(frozen=True, slots=True)
class RolePostingSample:
    """Bounded posting preview for Unknown or multi-label reporting."""

    job_title: str
    company_name: str | None
    role_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoleSmokeSummary:
    """Aggregate result of one bounded manual role-intelligence execution."""

    postings_considered: int
    new_analysis_runs: int
    existing_analysis_runs_reused: int
    evidence_created: int
    classified_postings: int
    unknown_postings: int
    multi_label_postings: int
    top_roles: tuple[RoleCount, ...]
    evidence_samples: tuple[RoleEvidenceSample, ...]
    unknown_samples: tuple[RolePostingSample, ...]
    multi_label_samples: tuple[RolePostingSample, ...]


def run_role_smoke(
    posting_reader: JobPostingReader,
    intelligence_repository: RoleIntelligenceRepository,
    *,
    limit: int,
    sample_limit: int = 10,
) -> RoleSmokeSummary:
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
    multi_label_postings = 0
    role_counts: dict[str, int] = {}
    role_names: dict[str, str] = {}
    evidence_samples: list[RoleEvidenceSample] = []
    unknown_samples: list[RolePostingSample] = []
    multi_label_samples: list[RolePostingSample] = []

    for posting in postings:
        result = analyze_job_roles(posting, intelligence_repository)
        if result.analysis_created:
            new_runs += 1
        else:
            reused_runs += 1
        evidence_created += result.evidence_created

        evidence = intelligence_repository.get_role_evidence(
            result.analysis_run_id
        )
        posting_role_codes = {item.role_code for item in evidence}
        if posting_role_codes:
            classified_postings += 1
        else:
            unknown_postings += 1
            if len(unknown_samples) < sample_limit:
                unknown_samples.append(
                    RolePostingSample(posting.title, posting.company_name)
                )

        if len(posting_role_codes) > 1:
            multi_label_postings += 1
            if len(multi_label_samples) < sample_limit:
                multi_label_samples.append(
                    RolePostingSample(
                        posting.title,
                        posting.company_name,
                        tuple(sorted(posting_role_codes)),
                    )
                )

        for item in evidence:
            existing_name = role_names.setdefault(item.role_code, item.role_name)
            if existing_name != item.role_name:
                raise ValueError(
                    f"conflicting display names for role code {item.role_code!r}"
                )
        for role_code in posting_role_codes:
            role_counts[role_code] = role_counts.get(role_code, 0) + 1

        remaining_samples = sample_limit - len(evidence_samples)
        if remaining_samples > 0:
            evidence_samples.extend(
                RoleEvidenceSample(
                    role_code=item.role_code,
                    role_name=item.role_name,
                    evidence_field=item.evidence_field.value,
                    matched_text=item.matched_text,
                    job_title=posting.title,
                    company_name=posting.company_name,
                    evidence_text=item.evidence_text,
                )
                for item in evidence[:remaining_samples]
            )

    top_roles = tuple(
        RoleCount(code, role_names[code], count)
        for code, count in sorted(
            role_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    return RoleSmokeSummary(
        postings_considered=len(postings),
        new_analysis_runs=new_runs,
        existing_analysis_runs_reused=reused_runs,
        evidence_created=evidence_created,
        classified_postings=classified_postings,
        unknown_postings=unknown_postings,
        multi_label_postings=multi_label_postings,
        top_roles=top_roles,
        evidence_samples=tuple(evidence_samples),
        unknown_samples=tuple(unknown_samples),
        multi_label_samples=tuple(multi_label_samples),
    )
