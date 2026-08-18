import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.remote_ok import (
    REMOTE_OK_USER_AGENT,
    RemoteOKCollector,
    RemoteOKFeedError,
)

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def test_collector_handles_metadata_and_collects_multiple_jobs() -> None:
    first_payload = {
        "id": "101",
        "position": "Python Developer",
        "company": "Example",
        "url": "https://remoteok.com/remote-jobs/remote-python-developer-101",
    }
    second_payload = {
        "id": 202,
        "position": "QA Engineer",
        "company": "Another",
        "url": "https://remoteok.com/remote-jobs/remote-qa-engineer-202",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://remote-ok.test/api"
        assert request.headers["user-agent"] == REMOTE_OK_USER_AGENT
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json=[
                {"last_updated": 123, "legal": "Link back to Remote OK"},
                first_payload,
                second_payload,
            ],
        )

    collector = RemoteOKCollector(
        base_url="https://remote-ok.test/",
        transport=httpx.MockTransport(handler),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 2
    assert result.failures == ()
    assert result.metadata == {
        "last_updated": 123,
        "legal": "Link back to Remote OK",
    }
    assert [job.external_id for job in result.jobs] == ["101", "202"]
    assert all(job.source_provider == "remote_ok" for job in result.jobs)
    assert all(job.source_scope == "global" for job in result.jobs)
    assert all(job.fetched_at == FETCHED_AT for job in result.jobs)
    assert str(result.jobs[0].source_url) == first_payload["url"]
    assert result.jobs[0].payload == first_payload
    assert result.jobs[1].payload == second_payload


def test_collector_keeps_first_job_when_metadata_header_is_absent() -> None:
    first_payload = {
        "id": "first-job",
        "position": "First Job",
        "url": "https://remoteok.com/remote-jobs/first-job",
    }
    collector = RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[first_payload],
                request=request,
            )
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 1
    assert result.metadata is None
    assert result.failures == ()
    assert [job.external_id for job in result.jobs] == ["first-job"]


def test_collector_accepts_empty_feed() -> None:
    collector = RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[], request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 0
    assert result.jobs == ()
    assert result.failures == ()
    assert result.metadata is None


def test_collector_reports_malformed_items_without_dropping_valid_jobs() -> None:
    valid_payload = {
        "id": "valid-1",
        "position": "Support Engineer",
        "url": "https://remoteok.com/remote-jobs/support-engineer-valid-1",
    }
    feed = [
        {"legal": "metadata"},
        {"position": "Missing ID", "url": "https://remoteok.com/jobs/missing"},
        "not-an-object",
        valid_payload,
    ]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=feed, request=request)
    )
    collector = RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=transport,
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 3
    assert [job.external_id for job in result.jobs] == ["valid-1"]
    assert len(result.failures) == 2
    assert [failure.item_index for failure in result.failures] == [1, 2]
    assert all(failure.stage == "collect" for failure in result.failures)
    assert "field 'id'" in result.failures[0].message
    assert "JSON object" in result.failures[1].message


def test_collector_raises_for_http_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, request=request)
    )
    collector = RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=transport,
        clock=lambda: FETCHED_AT,
    )

    with pytest.raises(httpx.HTTPStatusError) as error:
        asyncio.run(collector.collect())

    assert error.value.response.status_code == 503


@pytest.mark.parametrize("response_json", [{"jobs": []}, "not-a-list", None])
def test_collector_rejects_unsupported_top_level_shape(response_json: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if response_json is None:
            return httpx.Response(200, content=b"null", request=request)

        return httpx.Response(200, json=response_json, request=request)

    transport = httpx.MockTransport(handler)
    collector = RemoteOKCollector(
        base_url="https://remote-ok.test",
        transport=transport,
        clock=lambda: FETCHED_AT,
    )

    with pytest.raises(RemoteOKFeedError, match="JSON array"):
        asyncio.run(collector.collect())
