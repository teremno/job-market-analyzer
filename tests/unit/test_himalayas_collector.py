import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.himalayas import (
    HIMALAYAS_USER_AGENT,
    HimalayasCollector,
    HimalayasFeedError,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_collector_paginates_and_deduplicates_overlapping_native_guids() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        offset = int(request.url.params["offset"])
        identifiers = (0, 1) if offset == 0 else (1, 2)
        jobs = [
            {"guid": f"https://himalayas.app/jobs/{identifier}", "title": "Job"}
            for identifier in identifiers
        ]
        return httpx.Response(
            200,
            json={"jobs": jobs, "totalCount": 3, "offset": offset, "limit": 2},
            request=request,
        )

    result = asyncio.run(
        HimalayasCollector(
            base_url="https://himalayas.test",
            page_size=2,
            max_pages=2,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert result.fetched == 4
    assert [job.external_id for job in result.jobs] == [
        "https://himalayas.app/jobs/0",
        "https://himalayas.app/jobs/1",
        "https://himalayas.app/jobs/2",
    ]
    assert result.failures == ()
    assert [request.url.params["offset"] for request in requests] == ["0", "2"]
    assert all(request.headers["user-agent"] == HIMALAYAS_USER_AGENT for request in requests)
    assert result.metadata == {
        "totalCount": 3,
        "offset": 2,
        "limit": 2,
        "duplicates_skipped": 1,
    }


def test_collector_reports_malformed_item_and_keeps_valid_job() -> None:
    feed = {
        "jobs": [
            {"title": "Missing guid"},
            {"guid": "https://himalayas.app/jobs/valid", "title": "Valid"},
        ]
    }
    collector = HimalayasCollector(
        base_url="https://himalayas.test",
        page_size=20,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=feed, request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 2
    assert [job.external_id for job in result.jobs] == [
        "https://himalayas.app/jobs/valid"
    ]
    assert len(result.failures) == 1
    assert result.failures[0].stage == "collect"


def test_collector_propagates_network_error_and_rejects_bad_shape() -> None:
    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(httpx.ConnectError):
        asyncio.run(
            HimalayasCollector(
                base_url="https://himalayas.test",
                transport=httpx.MockTransport(network_failure),
            ).collect()
        )

    with pytest.raises(HimalayasFeedError, match="jobs array"):
        asyncio.run(
            HimalayasCollector(
                base_url="https://himalayas.test",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json={"results": []}, request=request
                    )
                ),
            ).collect()
        )
