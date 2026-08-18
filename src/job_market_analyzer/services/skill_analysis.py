"""Application service for deterministic skill analysis of current postings."""

from datetime import UTC, datetime

from job_market_analyzer.intelligence.hashing import calculate_skill_input_hash
from job_market_analyzer.intelligence.repository import (
    SKILL_ANALYZER_KIND,
    SkillAnalysisKey,
    SkillAnalysisPersistResult,
    SkillIntelligenceRepository,
)
from job_market_analyzer.intelligence.skills import (
    SKILL_TAXONOMY_VERSION,
    extract_skills,
)
from job_market_analyzer.models import JobPosting

def analyze_job_skills(
    posting: JobPosting,
    repository: SkillIntelligenceRepository,
) -> SkillAnalysisPersistResult:
    """Analyze the supplied current JobPosting state once per version and input."""

    input_hash = calculate_skill_input_hash(
        posting.title,
        posting.description_text,
        posting.source_tags,
    )
    key = SkillAnalysisKey(
        job_posting_id=posting.id,
        analyzer_kind=SKILL_ANALYZER_KIND,
        taxonomy_version=SKILL_TAXONOMY_VERSION,
        extractor_version=SKILL_TAXONOMY_VERSION,
        input_hash=input_hash,
    )
    existing_run_id = repository.find_analysis_run_id(key)
    if existing_run_id is not None:
        return SkillAnalysisPersistResult(
            analysis_run_id=existing_run_id,
            analysis_created=False,
            evidence_created=0,
        )

    evidence = extract_skills(
        posting.title,
        posting.description_text,
        posting.source_tags,
    )
    return repository.persist_skill_analysis(
        key,
        evidence,
        created_at=datetime.now(UTC),
    )
