import asyncio
import logging
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.web3_career import (
    WEB3_CAREER_TOKEN_ENV,
    WEB3_CAREER_USER_AGENT,
    Web3CareerAPIError,
    Web3CareerCollector,
    Web3CareerConfigurationError,
    Web3CareerFeedError,
)

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
TEST_TOKEN = "offline-test-token"


def test_collector_uses_official_query_and_extracts_nested_jobs() -> None:
    payload = {
        "id": 101,
        "date": "2026-08-17T10:30:00Z",
        "date_epoch": 1786962600,
        "is_remote": True,
        "country": None,
        "city": None,
        "title": "Solidity Engineer",
        "company": "Chain Labs",
        "location": "Worldwide",
        "apply_url": "https://web3.career/redirect/101?source=api",
        "tags": ["solidity", "smart-contracts"],
        "salary_min_value": 100000,
        "salary_max_value": 140000,
        "salary_currency": "USD",
        "salary_unit": "year",
        "estimated_min_salary": 95000,
        "estimated_max_salary": 145000,
        "estimated_avg_salary": 120000,
        "description": "<p>Build secure contracts.</p>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1"
        assert dict(request.url.params) == {
            "token": TEST_TOKEN,
            "remote": "true",
            "limit": "100",
            "show_description": "true",
        }
        assert request.headers["user-agent"] == WEB3_CAREER_USER_AGENT
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json=["web3.career", {"version": 1}, [payload]],
            request=request,
        )

    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(handler),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 1
    assert result.failures == ()
    assert result.metadata == {"root_items": ["web3.career", {"version": 1}]}
    assert result.jobs[0].source_provider == "web3_career"
    assert result.jobs[0].source_scope == "global"
    assert result.jobs[0].external_id == "101"
    assert result.jobs[0].source_url is None
    assert result.jobs[0].fetched_at == FETCHED_AT
    assert result.jobs[0].payload == payload
    assert result.jobs[0].payload["apply_url"] == payload["apply_url"]
    assert "token" not in result.jobs[0].payload
    assert TEST_TOKEN not in str(result.jobs[0].source_url)


def test_collector_accepts_explicit_null_source_url() -> None:
    payload = {
        "id": "null-url",
        "title": "Protocol Engineer",
        "apply_url": "https://web3.career/redirect/null-url",
        "url": None,
    }
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[payload], request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.failures == ()
    assert result.jobs[0].external_id == "null-url"
    assert result.jobs[0].source_url is None
    assert result.jobs[0].payload == payload


def test_collector_accepts_direct_jobs_array_fallback() -> None:
    payload = {
        "id": "direct-1",
        "title": "Protocol Engineer",
        "apply_url": "https://web3.career/redirect/direct-1",
        "url": "https://web3.career/protocol-engineer/direct-1",
    }
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[payload], request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 1
    assert result.metadata is None
    assert [job.external_id for job in result.jobs] == ["direct-1"]


def test_collector_reports_malformed_items_and_keeps_valid_jobs() -> None:
    valid_payload = {
        "id": "valid-1",
        "title": "Security Engineer",
        "apply_url": "https://web3.career/redirect/valid-1",
        "url": "https://web3.career/security-engineer/valid-1",
    }
    feed = [
        "metadata",
        [
            {
                "title": "Missing ID",
                "url": "https://web3.career/jobs/missing-id",
                "apply_url": "https://example.com/apply",
            },
            {
                "id": "missing-url",
                "title": "Missing URL",
                "apply_url": "https://example.com/apply",
            },
            {
                "id": "missing-apply-url",
                "title": "Missing Apply URL",
                "url": "https://web3.career/jobs/missing-apply-url",
            },
            "not-an-object",
            valid_payload,
        ],
    ]
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=feed, request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 5
    assert [job.external_id for job in result.jobs] == ["missing-url", "valid-1"]
    assert result.jobs[0].source_url is None
    assert len(result.failures) == 3
    assert [failure.item_index for failure in result.failures] == [0, 2, 3]
    assert all(failure.stage == "collect" for failure in result.failures)
    assert "field 'id'" in result.failures[0].message
    assert "field 'apply_url'" in result.failures[1].message
    assert "JSON object" in result.failures[2].message


def test_collector_rejects_non_string_optional_source_url() -> None:
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[
                    {
                        "id": "malformed-url",
                        "title": "Developer",
                        "apply_url": "https://web3.career/redirect/malformed-url",
                        "url": 123,
                    }
                ],
                request=request,
            )
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.jobs == ()
    assert len(result.failures) == 1
    assert "field 'url' must be a string" in result.failures[0].message


def test_collector_requires_token_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(WEB3_CAREER_TOKEN_ENV, raising=False)

    with pytest.raises(Web3CareerConfigurationError, match=WEB3_CAREER_TOKEN_ENV):
        Web3CareerCollector()


def test_collector_reads_token_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(WEB3_CAREER_TOKEN_ENV, TEST_TOKEN)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["token"] == TEST_TOKEN
        return httpx.Response(200, json=[], request=request)

    collector = Web3CareerCollector(
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(handler),
        clock=lambda: FETCHED_AT,
    )

    assert asyncio.run(collector.collect()).fetched == 0


def test_collector_http_error_does_not_expose_token() -> None:
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    with pytest.raises(Web3CareerAPIError, match="HTTP 429") as error:
        asyncio.run(collector.collect())

    assert TEST_TOKEN not in str(error.value)


def test_collector_redacts_token_from_httpx_info_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="httpx")
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[], request=request)
        ),
        clock=lambda: FETCHED_AT,
    )

    result = asyncio.run(collector.collect())

    assert result.fetched == 0
    assert TEST_TOKEN not in caplog.text
    assert "token=[REDACTED]" in caplog.text


@pytest.mark.parametrize("response_json", [{"jobs": []}, "not-a-list", None])
def test_collector_rejects_unsupported_top_level_shape(response_json: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if response_json is None:
            return httpx.Response(200, content=b"null", request=request)
        return httpx.Response(200, json=response_json, request=request)

    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(handler),
        clock=lambda: FETCHED_AT,
    )

    with pytest.raises(Web3CareerFeedError, match="JSON array"):
        asyncio.run(collector.collect())


def test_collector_rejects_mixed_root_without_jobs_array() -> None:
    collector = Web3CareerCollector(
        api_token=TEST_TOKEN,
        base_url="https://web3-career.test/api",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=["metadata", {"version": 1}],
                request=request,
            )
        ),
        clock=lambda: FETCHED_AT,
    )

    with pytest.raises(Web3CareerFeedError, match="does not contain a jobs array"):
        asyncio.run(collector.collect())
