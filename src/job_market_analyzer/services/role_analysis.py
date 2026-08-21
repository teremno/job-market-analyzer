"""Application service for deterministic role analysis of current postings."""

from datetime import UTC, datetime

from job_market_analyzer.intelligence.hashing import calculate_role_input_hash
from job_market_analyzer.intelligence.repository import (
    ROLE_ANALYZER_KIND,
    RoleAnalysisKey,
    RoleAnalysisPersistResult,
    RoleIntelligenceRepository,
)
from job_market_analyzer.intelligence.roles import (
    ROLE_TAXONOMY_VERSION,
    extract_roles,
)
from job_market_analyzer.models import JobPosting


def analyze_job_roles(
    posting: JobPosting,
    repository: RoleIntelligenceRepository,
) -> RoleAnalysisPersistResult:
    """Analyze trusted current persisted state once per version and input.

    The caller owns freshness: a stale ``JobPosting`` creates a valid historical
    run for that stale title and description.
    """

    input_hash = calculate_role_input_hash(
        posting.title,
        posting.description_text,
    )
    key = RoleAnalysisKey(
        job_posting_id=posting.id,
        analyzer_kind=ROLE_ANALYZER_KIND,
        taxonomy_version=ROLE_TAXONOMY_VERSION,
        extractor_version=ROLE_TAXONOMY_VERSION,
        input_hash=input_hash,
    )
    existing_run_id = repository.find_analysis_run_id(key)
    if existing_run_id is not None:
        return RoleAnalysisPersistResult(
            analysis_run_id=existing_run_id,
            analysis_created=False,
            evidence_created=0,
        )

    evidence = extract_roles(posting.title, posting.description_text)
    return repository.persist_role_analysis(
        key,
        evidence,
        created_at=datetime.now(UTC),
    )
