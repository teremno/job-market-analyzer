import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.base import JobCollector
from job_market_analyzer.collectors.himalayas import HimalayasCollector
from job_market_analyzer.collectors.jobicy import JobicyCollector
from job_market_analyzer.collectors.remotive import RemotiveCollector
from job_market_analyzer.collectors.we_work_remotely import WeWorkRemotelyCollector
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.normalization.himalayas import normalize_himalayas_job
from job_market_analyzer.normalization.jobicy import normalize_jobicy_job
from job_market_analyzer.normalization.remotive import normalize_remotive_job
from job_market_analyzer.normalization.we_work_remotely import (
    normalize_we_work_remotely_job,
)
from job_market_analyzer.services.collection import collect_and_persist_jobs
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FIRST_FETCH = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
SECOND_FETCH = datetime(2026, 8, 21, 13, 0, tzinfo=UTC)
Normalizer = Callable[[RawJob], NormalizedJobPosting]
CaseFactory = Callable[[], tuple[JobCollector, Normalizer, str]]


def himalayas_case() -> tuple[JobCollector, Normalizer, str]:
    times = iter((FIRST_FETCH, SECOND_FETCH))
    feed = {
        "jobs": [
            {
                "guid": "https://himalayas.app/jobs/stable",
                "title": "Stable Backend Engineer",
                "companyName": "Example",
                "description": "<p>Build APIs.</p>",
            }
        ]
    }
    return (
        HimalayasCollector(
            base_url="https://himalayas.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=feed, request=request)
            ),
            clock=lambda: next(times),
        ),
        normalize_himalayas_job,
        "himalayas",
    )


def jobicy_case() -> tuple[JobCollector, Normalizer, str]:
    times = iter((FIRST_FETCH, SECOND_FETCH))
    feed = {
        "jobs": [
            {
                "id": "stable",
                "url": "https://jobicy.com/jobs/stable",
                "jobTitle": "Stable Backend Engineer",
            }
        ]
    }
    return (
        JobicyCollector(
            base_url="https://jobicy.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=feed, request=request)
            ),
            clock=lambda: next(times),
        ),
        normalize_jobicy_job,
        "jobicy",
    )


def remotive_case() -> tuple[JobCollector, Normalizer, str]:
    times = iter((FIRST_FETCH, SECOND_FETCH))
    feed = {
        "jobs": [
            {
                "id": "stable",
                "url": "https://remotive.com/remote-jobs/stable",
                "title": "Stable Backend Engineer",
            }
        ]
    }
    return (
        RemotiveCollector(
            base_url="https://remotive.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=feed, request=request)
            ),
            clock=lambda: next(times),
        ),
        normalize_remotive_job,
        "remotive",
    )


def wwr_case() -> tuple[JobCollector, Normalizer, str]:
    times = iter((FIRST_FETCH, SECOND_FETCH))
    url = "https://weworkremotely.com/remote-jobs/stable"
    feed = (
        "<rss><channel><item>"
        f"<guid>{url}</guid><link>{url}</link>"
        "<title>Example: Stable Backend Engineer</title>"
        "</item></channel></rss>"
    ).encode()
    return (
        WeWorkRemotelyCollector(
            base_url="https://wwr.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=feed, request=request)
            ),
            clock=lambda: next(times),
        ),
        normalize_we_work_remotely_job,
        "we_work_remotely",
    )


@pytest.mark.parametrize(
    "case_factory",
    [himalayas_case, jobicy_case, remotive_case, wwr_case],
    ids=["himalayas", "jobicy", "remotive", "we-work-remotely"],
)
def test_new_source_repeated_feed_uses_generic_idempotent_sqlite_pipeline(
    case_factory: CaseFactory,
) -> None:
    collector, normalizer, provider = case_factory()
    connection = connect_database(":memory:")
    initialize_database(connection)
    repository = SQLiteJobRepository(connection)
    try:
        first = asyncio.run(
            collect_and_persist_jobs(collector, normalizer, repository)
        )
        second = asyncio.run(
            collect_and_persist_jobs(collector, normalizer, repository)
        )

        assert (first.fetched, first.persisted, first.failed) == (1, 1, 0)
        assert (first.postings_created, first.raw_observations_created) == (1, 1)
        assert (second.fetched, second.persisted, second.failed) == (1, 1, 0)
        assert (second.postings_created, second.raw_observations_created) == (0, 0)
        assert connection.execute(
            "SELECT source_provider FROM job_postings"
        ).fetchone()[0] == provider
        assert connection.execute("SELECT COUNT(*) FROM canonical_jobs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0] == 1
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
    finally:
        connection.close()
