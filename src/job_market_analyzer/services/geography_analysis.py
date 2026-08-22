"""Application service for deterministic geography analysis of postings."""

from datetime import UTC, datetime

from job_market_analyzer.intelligence.geography import (
    GEOGRAPHY_TAXONOMY_VERSION,
    extract_geography,
)
from job_market_analyzer.intelligence.hashing import calculate_geography_input_hash
from job_market_analyzer.intelligence.repository import (
    GEOGRAPHY_ANALYZER_KIND,
    GeographyAnalysisKey,
    GeographyAnalysisPersistResult,
    GeographyIntelligenceRepository,
)
from job_market_analyzer.models import JobPosting


def analyze_job_geography(
    posting: JobPosting,
    repository: GeographyIntelligenceRepository,
) -> GeographyAnalysisPersistResult:
    """Analyze trusted current persisted state once per version and input.

    The analyzer consumes normalized ``description_text``, ``location_text``
    and the structured ``is_remote`` flag; title changes intentionally do not
    create new geography runs. Zero evidence is a successful persisted run
    without evidence (Unknown), distinct from a posting never analyzed.
    """

    input_hash = calculate_geography_input_hash(
        posting.description_text,
        location_text=posting.location_text,
        is_remote=posting.is_remote,
    )
    key = GeographyAnalysisKey(
        job_posting_id=posting.id,
        analyzer_kind=GEOGRAPHY_ANALYZER_KIND,
        taxonomy_version=GEOGRAPHY_TAXONOMY_VERSION,
        extractor_version=GEOGRAPHY_TAXONOMY_VERSION,
        input_hash=input_hash,
    )
    existing_run_id = repository.find_analysis_run_id(key)
    if existing_run_id is not None:
        return GeographyAnalysisPersistResult(
            analysis_run_id=existing_run_id,
            analysis_created=False,
            evidence_created=0,
        )

    evidence = extract_geography(
        posting.description_text,
        location_text=posting.location_text,
        is_remote=posting.is_remote,
    )
    return repository.persist_geography_analysis(
        key,
        evidence,
        created_at=datetime.now(UTC),
    )
