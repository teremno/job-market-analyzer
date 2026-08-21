import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.remotive import (
    REMOTIVE_USER_AGENT,
    RemotiveCollector,
    RemotiveFeedError,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_collector_uses_public_limit_and_preserves_attributed_url() -> None:
    payload = {
        "id": 101,
        "url": "https://remotive.com/remote-jobs/software-dev/example-101",
        "title": "Example",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "50"
        assert request.headers["user-agent"] == REMOTIVE_USER_AGENT
        return httpx.Response(
            200,
            json={"jobs": [payload], "job-count": 1, "0-legal-notice": "link back"},
            request=request,
        )

    result = asyncio.run(
        RemotiveCollector(
            base_url="https://remotive.test",
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert result.fetched == 1
    assert result.jobs[0].external_id == "101"
    assert str(result.jobs[0].source_url) == payload["url"]
    assert result.metadata == {"job-count": 1, "0-legal-notice": "link back"}


def test_collector_keeps_valid_item_after_malformed_item() -> None:
    feed = {
        "jobs": [
            {"id": "bad"},
            {"id": "valid", "url": "https://remotive.com/remote-jobs/valid"},
        ]
    }
    result = asyncio.run(
        RemotiveCollector(
            base_url="https://remotive.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=feed, request=request)
            ),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert [job.external_id for job in result.jobs] == ["valid"]
    assert len(result.failures) == 1
    assert result.failures[0].external_id == "bad"


def test_collector_network_and_shape_failures_propagate() -> None:
    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(httpx.ConnectError):
        asyncio.run(
            RemotiveCollector(
                base_url="https://remotive.test",
                transport=httpx.MockTransport(network_failure),
            ).collect()
        )
    with pytest.raises(RemotiveFeedError, match="jobs array"):
        asyncio.run(
            RemotiveCollector(
                base_url="https://remotive.test",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json={"results": []}, request=request
                    )
                ),
            ).collect()
        )
