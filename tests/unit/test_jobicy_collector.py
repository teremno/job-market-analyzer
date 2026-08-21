import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.jobicy import (
    JOBICY_USER_AGENT,
    JobicyCollector,
    JobicyFeedError,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_collector_uses_public_count_and_native_id() -> None:
    payload = {
        "id": 101,
        "url": "https://jobicy.com/jobs/101-example",
        "jobTitle": "Example",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["count"] == "25"
        assert request.headers["user-agent"] == JOBICY_USER_AGENT
        return httpx.Response(
            200,
            json={"jobs": [payload], "jobCount": 1, "apiVersion": "2"},
            request=request,
        )

    result = asyncio.run(
        JobicyCollector(
            base_url="https://jobicy.test",
            count=25,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert result.fetched == 1
    assert result.jobs[0].external_id == "101"
    assert str(result.jobs[0].source_url) == payload["url"]
    assert result.jobs[0].payload == payload
    assert result.metadata == {"jobCount": 1, "apiVersion": "2"}


def test_collector_reports_bad_item_without_losing_valid_item() -> None:
    feed = {
        "jobs": [
            {"id": "missing-url"},
            {"id": "valid", "url": "https://jobicy.com/jobs/valid"},
        ]
    }
    result = asyncio.run(
        JobicyCollector(
            base_url="https://jobicy.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=feed, request=request)
            ),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert result.fetched == 2
    assert [job.external_id for job in result.jobs] == ["valid"]
    assert len(result.failures) == 1
    assert result.failures[0].external_id == "missing-url"


def test_collector_network_and_shape_failures_are_systemic() -> None:
    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(
            JobicyCollector(
                base_url="https://jobicy.test",
                transport=httpx.MockTransport(network_failure),
            ).collect()
        )
    with pytest.raises(JobicyFeedError, match="jobs array"):
        asyncio.run(
            JobicyCollector(
                base_url="https://jobicy.test",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=[], request=request)
                ),
            ).collect()
        )
