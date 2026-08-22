"""Application service for deterministic seniority analysis of postings."""

from datetime import UTC, datetime

from job_market_analyzer.intelligence.hashing import calculate_seniority_input_hash
from job_market_analyzer.intelligence.repository import (
    SENIORITY_ANALYZER_KIND,
    SeniorityAnalysisKey,
    SeniorityAnalysisPersistResult,
    SeniorityIntelligenceRepository,
)
from job_market_analyzer.intelligence.seniority import (
    SENIORITY_TAXONOMY_VERSION,
    extract_seniority,
)
from job_market_analyzer.models import JobPosting


def analyze_job_seniority(
    posting: JobPosting,
    repository: SeniorityIntelligenceRepository,
) -> SeniorityAnalysisPersistResult:
    """Analyze trusted current persisted title once per version and input.

    Seniority v1 is a title-only analyzer: a changed description does not
    create a new run. Zero evidence is a successful persisted run without
    evidence (Unknown), distinct from a posting never analyzed.
    """

    input_hash = calculate_seniority_input_hash(posting.title)
    key = SeniorityAnalysisKey(
        job_posting_id=posting.id,
        analyzer_kind=SENIORITY_ANALYZER_KIND,
        taxonomy_version=SENIORITY_TAXONOMY_VERSION,
        extractor_version=SENIORITY_TAXONOMY_VERSION,
        input_hash=input_hash,
    )
    existing_run_id = repository.find_analysis_run_id(key)
    if existing_run_id is not None:
        return SeniorityAnalysisPersistResult(
            analysis_run_id=existing_run_id,
            analysis_created=False,
            evidence_created=0,
        )

    evidence = extract_seniority(posting.title)
    return repository.persist_seniority_analysis(
        key,
        evidence,
        created_at=datetime.now(UTC),
    )
