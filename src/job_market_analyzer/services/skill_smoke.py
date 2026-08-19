"""Bounded one-shot skill intelligence over current durable postings."""

from dataclasses import dataclass

from job_market_analyzer.intelligence.models import EvidenceField
from job_market_analyzer.intelligence.repository import SkillIntelligenceRepository
from job_market_analyzer.intelligence.skills import extract_skills
from job_market_analyzer.services.skill_analysis import analyze_job_skills
from job_market_analyzer.storage.repository import JobPostingReader


@dataclass(frozen=True, slots=True)
class SkillCount:
    """Posting-level count for one canonical skill in the execution scope."""

    name: str
    postings: int


@dataclass(frozen=True, slots=True)
class SourceTagCount:
    """Unrecognized source tag count in the execution scope."""

    tag: str
    postings: int


@dataclass(frozen=True, slots=True)
class SkillEvidenceSample:
    """Safe, bounded evidence preview tied to its current posting."""

    skill_name: str
    evidence_field: str
    matched_alias: str
    job_title: str
    company_name: str | None
    evidence_text: str


@dataclass(frozen=True, slots=True)
class SkillSmokeSummary:
    """Aggregate result of one bounded manual intelligence execution."""

    postings_considered: int
    new_analysis_runs: int
    existing_analysis_runs_reused: int
    evidence_created: int
    zero_skill_runs: int
    postings_with_skills: int
    top_skills: tuple[SkillCount, ...]
    unrecognized_source_tags: tuple[SourceTagCount, ...]
    evidence_samples: tuple[SkillEvidenceSample, ...]


def run_skill_smoke(
    posting_reader: JobPostingReader,
    intelligence_repository: SkillIntelligenceRepository,
    *,
    limit: int,
    sample_limit: int = 10,
) -> SkillSmokeSummary:
    """Analyze one deterministic current-posting scope without swallowing errors."""

    if limit < 1:
        raise ValueError("limit must be greater than zero")
    if sample_limit < 0:
        raise ValueError("sample_limit must not be negative")

    postings = posting_reader.list_job_postings(limit=limit)
    new_runs = 0
    reused_runs = 0
    evidence_created = 0
    zero_skill_runs = 0
    postings_with_skills = 0
    skill_counts: dict[str, int] = {}
    skill_names: dict[str, str] = {}
    unrecognized_tags: dict[str, int] = {}
    samples: list[SkillEvidenceSample] = []

    for posting in postings:
        result = analyze_job_skills(posting, intelligence_repository)
        if result.analysis_created:
            new_runs += 1
        else:
            reused_runs += 1
        evidence_created += result.evidence_created

        evidence = intelligence_repository.get_skill_evidence(
            result.analysis_run_id
        )
        posting_skill_codes = {item.skill_code for item in evidence}
        if posting_skill_codes:
            postings_with_skills += 1
        else:
            zero_skill_runs += 1

        for item in evidence:
            existing_name = skill_names.setdefault(
                item.skill_code,
                item.skill_name,
            )
            if existing_name != item.skill_name:
                raise ValueError(
                    f"conflicting display names for skill code {item.skill_code!r}"
                )
        for skill_code in posting_skill_codes:
            skill_counts[skill_code] = skill_counts.get(skill_code, 0) + 1

        for tag in posting.source_tags:
            tag_evidence = extract_skills("", None, (tag,))
            if not any(
                item.evidence_field is EvidenceField.TAG
                for item in tag_evidence
            ):
                unrecognized_tags[tag] = unrecognized_tags.get(tag, 0) + 1

        remaining_samples = sample_limit - len(samples)
        if remaining_samples > 0:
            samples.extend(
                SkillEvidenceSample(
                    skill_name=item.skill_name,
                    evidence_field=item.evidence_field.value,
                    matched_alias=item.matched_alias,
                    job_title=posting.title,
                    company_name=posting.company_name,
                    evidence_text=item.evidence_text,
                )
                for item in evidence[:remaining_samples]
            )

    top_skills = tuple(
        SkillCount(skill_names[code], count)
        for code, count in sorted(
            skill_counts.items(),
            key=lambda item: (
                -item[1],
                skill_names[item[0]].casefold(),
                item[0],
            ),
        )
    )
    source_tag_counts = tuple(
        SourceTagCount(tag, count)
        for tag, count in sorted(
            unrecognized_tags.items(),
            key=lambda item: (-item[1], item[0].casefold(), item[0]),
        )
    )
    return SkillSmokeSummary(
        postings_considered=len(postings),
        new_analysis_runs=new_runs,
        existing_analysis_runs_reused=reused_runs,
        evidence_created=evidence_created,
        zero_skill_runs=zero_skill_runs,
        postings_with_skills=postings_with_skills,
        top_skills=top_skills,
        unrecognized_source_tags=source_tag_counts,
        evidence_samples=tuple(samples),
    )
