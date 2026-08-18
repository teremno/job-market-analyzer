import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from job_market_analyzer.collectors.remote_ok import RemoteOKCollector
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.normalization.remote_ok import normalize_remote_ok_job
from job_market_analyzer.services.collection import collect_and_persist_jobs
from job_market_analyzer.storage.repository import PersistResult
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
SECOND_FETCHED_AT = datetime(2026, 8, 18, 13, 0, tzinfo=UTC)


class FakeJobRepository:
    def __init__(self, *, failing_external_ids: set[str] | None = None) -> None:
        self.failing_external_ids = failing_external_ids or set()
        self.attempted_external_ids: list[str] = []
        self.persisted_external_ids: list[str] = []

    def persist_observation(
        self,
        raw_job: RawJob,
        posting: NormalizedJobPosting,
    ) -> PersistResult:
        assert raw_job.external_id == posting.external_id
        self.attempted_external_ids.append(raw_job.external_id)

        if raw_job.external_id in self.failing_external_ids:
            raise RuntimeError("forced repository failure")

        self.persisted_external_ids.append(raw_job.external_id)
        created = raw_job.external_id == "new"
        return PersistResult(
            canonical_job_id=uuid4(),
            job_posting_id=uuid4(),
            raw_job_id=raw_job.id if created else None,
            canonical_created=created,
            posting_created=created,
            raw_observation_created=created,
        )


def make_collector(feed: list[object]) -> RemoteOKCollector:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=feed, request=request)
    )
    return RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=transport,
        clock=lambda: FETCHED_AT,
    )


def make_job(external_id: str, title: str) -> dict[str, object]:
    return {
        "id": external_id,
        "position": title,
        "company": "Example Company",
        "url": f"https://remoteok.com/remote-jobs/{external_id}",
        "date": "2026-08-17T10:30:00+00:00",
    }


def test_collection_service_counts_multiple_successful_jobs() -> None:
    collector = make_collector(
        [
            {"legal": "metadata"},
            make_job("new", "New Job"),
            make_job("existing", "Existing Job"),
        ]
    )
    repository = FakeJobRepository()

    summary = asyncio.run(
        collect_and_persist_jobs(
            collector,
            normalize_remote_ok_job,
            repository,
        )
    )

    assert summary.fetched == 2
    assert summary.persisted == 2
    assert summary.postings_created == 1
    assert summary.raw_observations_created == 1
    assert summary.failed == 0
    assert summary.failures == ()
    assert repository.persisted_external_ids == ["new", "existing"]


def test_collection_service_continues_after_collector_item_failure() -> None:
    collector = make_collector(
        [
            {"last_updated": 123},
            {"position": "Missing ID", "url": "https://remoteok.com/jobs/missing"},
            make_job("new", "Successful Job"),
        ]
    )
    repository = FakeJobRepository()

    summary = asyncio.run(
        collect_and_persist_jobs(
            collector,
            normalize_remote_ok_job,
            repository,
        )
    )

    assert summary.fetched == 2
    assert summary.persisted == 1
    assert summary.postings_created == 1
    assert summary.raw_observations_created == 1
    assert summary.failed == 1
    assert [failure.stage for failure in summary.failures] == ["collect"]
    assert repository.attempted_external_ids == ["new"]
    assert repository.persisted_external_ids == ["new"]


def test_collection_service_continues_after_normalization_failure() -> None:
    missing_title = make_job("missing-title", "Temporary title")
    del missing_title["position"]
    collector = make_collector(
        [
            {"legal": "metadata"},
            missing_title,
            make_job("new", "Successful Job"),
        ]
    )
    repository = FakeJobRepository()

    summary = asyncio.run(
        collect_and_persist_jobs(
            collector,
            normalize_remote_ok_job,
            repository,
        )
    )

    assert summary.fetched == 2
    assert summary.persisted == 1
    assert summary.postings_created == 1
    assert summary.raw_observations_created == 1
    assert summary.failed == 1
    assert summary.failures[0].stage == "normalize"
    assert summary.failures[0].external_id == "missing-title"
    assert summary.failures[0].message.startswith("RemoteOKNormalizationError:")
    assert repository.attempted_external_ids == ["new"]
    assert repository.persisted_external_ids == ["new"]


def test_collection_service_propagates_unexpected_normalizer_exception() -> None:
    collector = make_collector(
        [
            make_job("broken", "Broken Job"),
            make_job("new", "Later Job"),
        ]
    )
    repository = FakeJobRepository()

    def broken_normalizer(raw_job: RawJob) -> NormalizedJobPosting:
        del raw_job
        raise RuntimeError("normalizer programming defect")

    with pytest.raises(RuntimeError, match="normalizer programming defect"):
        asyncio.run(
            collect_and_persist_jobs(
                collector,
                broken_normalizer,
                repository,
            )
        )

    assert repository.attempted_external_ids == []
    assert repository.persisted_external_ids == []


def test_collection_service_propagates_repository_exception_and_stops() -> None:
    collector = make_collector(
        [
            make_job("fails", "Repository Failure"),
            make_job("new", "Later Job"),
        ]
    )
    repository = FakeJobRepository(failing_external_ids={"fails"})

    with pytest.raises(RuntimeError, match="forced repository failure"):
        asyncio.run(
            collect_and_persist_jobs(
                collector,
                normalize_remote_ok_job,
                repository,
            )
        )

    assert repository.attempted_external_ids == ["fails"]
    assert repository.persisted_external_ids == []


def test_repeated_remote_ok_feed_is_idempotent_with_real_sqlite_repository() -> None:
    feed = [
        {"legal": "metadata"},
        make_job("stable-job", "Stable Job"),
    ]
    fetch_times = iter((FETCHED_AT, SECOND_FETCHED_AT))
    collector = RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=feed, request=request)
        ),
        clock=lambda: next(fetch_times),
    )
    connection = connect_database(":memory:")
    initialize_database(connection)
    repository = SQLiteJobRepository(connection)

    try:
        first_summary = asyncio.run(
            collect_and_persist_jobs(
                collector,
                normalize_remote_ok_job,
                repository,
            )
        )
        first_posting = dict(
            connection.execute(
                """
                SELECT id, canonical_job_id, first_seen_at, last_seen_at
                FROM job_postings
                """
            ).fetchone()
        )

        second_summary = asyncio.run(
            collect_and_persist_jobs(
                collector,
                normalize_remote_ok_job,
                repository,
            )
        )
        second_posting = dict(
            connection.execute(
                """
                SELECT id, canonical_job_id, first_seen_at, last_seen_at
                FROM job_postings
                """
            ).fetchone()
        )
        raw_posting_id = connection.execute(
            "SELECT job_posting_id FROM raw_jobs"
        ).fetchone()["job_posting_id"]

        assert first_summary.postings_created == 1
        assert first_summary.raw_observations_created == 1
        assert first_summary.failed == 0
        assert second_summary.postings_created == 0
        assert second_summary.raw_observations_created == 0
        assert second_summary.failed == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM job_postings"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_jobs"
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM raw_jobs").fetchone()[0] == 1
        assert second_posting["id"] == first_posting["id"]
        assert second_posting["canonical_job_id"] == first_posting["canonical_job_id"]
        assert raw_posting_id == first_posting["id"]
        assert second_posting["first_seen_at"] == first_posting["first_seen_at"]
        assert first_posting["last_seen_at"] == "2026-08-18T12:00:00.000000Z"
        assert second_posting["last_seen_at"] == "2026-08-18T13:00:00.000000Z"
    finally:
        connection.close()
