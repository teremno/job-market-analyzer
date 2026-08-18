import asyncio
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.web3_career import Web3CareerCollector
from job_market_analyzer.normalization.web3_career import normalize_web3_career_job
from job_market_analyzer.services.collection import collect_and_persist_jobs
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

FIRST_FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
SECOND_FETCHED_AT = datetime(2026, 8, 18, 13, 0, tzinfo=UTC)


def test_repeated_web3_feed_is_idempotent_with_real_sqlite_repository() -> None:
    apply_url = "https://web3.career/redirect/stable-job?source=api"
    source_url = "https://web3.career/stable-web3-job/stable-job"
    test_token = "offline-test-token"
    feed = [
        "metadata",
        [
            {
                "id": "stable-job",
                "title": "Stable Web3 Job",
                "company": "Example Company",
                "remote": True,
                "location": "Worldwide",
                "apply_url": apply_url,
                "url": source_url,
                "date": "2026-08-17T10:30:00Z",
            }
        ],
    ]
    fetch_times = iter((FIRST_FETCHED_AT, SECOND_FETCHED_AT))
    collector = Web3CareerCollector(
        api_token=test_token,
        base_url="https://web3-career.test/api",
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
                normalize_web3_career_job,
                repository,
            )
        )
        first_posting = dict(
            connection.execute(
                """
                SELECT id, canonical_job_id, source_url, application_url,
                       first_seen_at, last_seen_at
                FROM job_postings
                """
            ).fetchone()
        )

        second_summary = asyncio.run(
            collect_and_persist_jobs(
                collector,
                normalize_web3_career_job,
                repository,
            )
        )
        second_posting = dict(
            connection.execute(
                """
                SELECT id, canonical_job_id, source_url, application_url,
                       first_seen_at, last_seen_at
                FROM job_postings
                """
            ).fetchone()
        )
        raw_posting_id = connection.execute(
            "SELECT job_posting_id FROM raw_jobs"
        ).fetchone()["job_posting_id"]
        raw_observation = dict(
            connection.execute(
                "SELECT source_url, payload_json FROM raw_jobs"
            ).fetchone()
        )

        assert first_summary.fetched == 1
        assert first_summary.persisted == 1
        assert first_summary.postings_created == 1
        assert first_summary.raw_observations_created == 1
        assert first_summary.failed == 0
        assert second_summary.fetched == 1
        assert second_summary.persisted == 1
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
        assert first_posting["source_url"] == source_url
        assert first_posting["application_url"] == apply_url
        assert raw_observation["source_url"] == source_url
        assert test_token not in raw_observation["source_url"]
        assert test_token not in raw_observation["payload_json"]
        assert test_token not in first_posting["source_url"]
        assert test_token not in first_posting["application_url"]
        assert second_posting["first_seen_at"] == first_posting["first_seen_at"]
        assert first_posting["last_seen_at"] == "2026-08-18T12:00:00.000000Z"
        assert second_posting["last_seen_at"] == "2026-08-18T13:00:00.000000Z"
    finally:
        connection.close()
