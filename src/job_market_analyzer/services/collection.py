"""Reusable collection orchestration independent from concrete storage."""

from collections.abc import Callable
from dataclasses import dataclass

from job_market_analyzer.collectors.base import (
    CollectionFailure,
    FailureStage,
    JobCollector,
)
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.normalization.jobs import NormalizationError
from job_market_analyzer.storage.repository import JobRepository

JobNormalizer = Callable[[RawJob], NormalizedJobPosting]


@dataclass(frozen=True)
class CollectionSummary:
    """Counts and item failures from one source collection run."""

    fetched: int
    persisted: int
    postings_created: int
    raw_observations_created: int
    failed: int
    failures: tuple[CollectionFailure, ...]


async def collect_and_persist_jobs(
    collector: JobCollector,
    normalizer: JobNormalizer,
    repository: JobRepository,
) -> CollectionSummary:
    """
    Collect, normalize, and persist one source batch.

    Source-wide failures and systemic application/storage errors propagate. Collector
    item failures and typed recoverable normalization failures are reported while later
    valid items continue. Each repository call remains an atomic persistence operation.
    """

    collected = await collector.collect()
    failures = list(collected.failures)
    persisted = 0
    postings_created = 0
    raw_observations_created = 0

    for raw_job in collected.jobs:
        try:
            posting = normalizer(raw_job)
        except NormalizationError as exc:
            failures.append(
                _item_failure(raw_job, stage="normalize", exception=exc)
            )
            continue

        result = repository.persist_observation(raw_job, posting)

        persisted += 1
        postings_created += int(result.posting_created)
        raw_observations_created += int(result.raw_observation_created)

    return CollectionSummary(
        fetched=collected.fetched,
        persisted=persisted,
        postings_created=postings_created,
        raw_observations_created=raw_observations_created,
        failed=len(failures),
        failures=tuple(failures),
    )


def _item_failure(
    raw_job: RawJob,
    *,
    stage: FailureStage,
    exception: Exception,
) -> CollectionFailure:
    return CollectionFailure(
        source_provider=raw_job.source_provider,
        stage=stage,
        external_id=raw_job.external_id,
        message=f"{type(exception).__name__}: {exception}",
    )
