"""Application service for deterministic salary analysis of postings."""

from datetime import UTC, datetime

from job_market_analyzer.intelligence.hashing import calculate_salary_input_hash
from job_market_analyzer.intelligence.repository import (
    SALARY_ANALYZER_KIND,
    SalaryAnalysisKey,
    SalaryAnalysisPersistResult,
    SalaryIntelligenceRepository,
)
from job_market_analyzer.intelligence.salaries import (
    SALARY_TAXONOMY_VERSION,
    extract_salary_estimate,
)
from job_market_analyzer.models import JobPosting


def analyze_job_salary(
    posting: JobPosting,
    repository: SalaryIntelligenceRepository,
) -> SalaryAnalysisPersistResult:
    """Analyze trusted current persisted state once per version and input.

    The analyzer consumes only the normalized salary fields. Zero estimate is
    a successful persisted run without an estimate (no salary data), distinct
    from a posting never analyzed.
    """

    input_hash = calculate_salary_input_hash(
        posting.salary_text,
        salary_min=str(posting.salary_min) if posting.salary_min else None,
        salary_max=str(posting.salary_max) if posting.salary_max else None,
        salary_currency=posting.salary_currency,
        salary_period=posting.salary_period.value if posting.salary_period else None,
    )
    key = SalaryAnalysisKey(
        job_posting_id=posting.id,
        analyzer_kind=SALARY_ANALYZER_KIND,
        taxonomy_version=SALARY_TAXONOMY_VERSION,
        extractor_version=SALARY_TAXONOMY_VERSION,
        input_hash=input_hash,
    )
    existing_run_id = repository.find_analysis_run_id(key)
    if existing_run_id is not None:
        return SalaryAnalysisPersistResult(
            analysis_run_id=existing_run_id,
            analysis_created=False,
            estimate_created=False,
        )

    estimates = extract_salary_estimate(
        posting.salary_text,
        salary_min=posting.salary_min,
        salary_max=posting.salary_max,
        salary_currency=posting.salary_currency,
        salary_period=posting.salary_period.value if posting.salary_period else None,
    )
    estimate = estimates[0] if estimates else None
    return repository.persist_salary_analysis(
        key,
        estimate,
        created_at=datetime.now(UTC),
    )
