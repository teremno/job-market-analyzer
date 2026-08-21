import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.we_work_remotely import (
    WE_WORK_REMOTELY_USER_AGENT,
    WeWorkRemotelyCollector,
    WeWorkRemotelyFeedError,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def rss(*items: str) -> bytes:
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode()


def item(guid: str | None, title: str = "Company: Job") -> str:
    guid_xml = f"<guid>{guid}</guid><link>{guid}</link>" if guid else ""
    return f"<item><title>{title}</title>{guid_xml}<description>x</description></item>"


def test_collector_parses_official_rss_and_honors_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == WE_WORK_REMOTELY_USER_AGENT
        assert "application/rss+xml" in request.headers["accept"]
        return httpx.Response(
            200,
            content=rss(
                item("https://weworkremotely.com/remote-jobs/one"),
                item("https://weworkremotely.com/remote-jobs/two"),
            ),
            request=request,
        )

    result = asyncio.run(
        WeWorkRemotelyCollector(
            base_url="https://wwr.test",
            limit=1,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert result.fetched == 1
    assert result.jobs[0].external_id.endswith("/one")
    assert result.jobs[0].payload["title"] == "Company: Job"


def test_collector_reports_malformed_rss_item_and_keeps_valid_item() -> None:
    result = asyncio.run(
        WeWorkRemotelyCollector(
            base_url="https://wwr.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    content=rss(
                        item(None),
                        item("https://weworkremotely.com/remote-jobs/valid"),
                        item("https://weworkremotely.com/remote-jobs/valid"),
                    ),
                    request=request,
                )
            ),
            clock=lambda: FETCHED_AT,
        ).collect()
    )

    assert result.fetched == 3
    assert len(result.jobs) == 1
    assert len(result.failures) == 1
    assert result.metadata == {"duplicates_skipped": 1}


def test_collector_rejects_invalid_xml_and_propagates_network_error() -> None:
    with pytest.raises(WeWorkRemotelyFeedError, match="invalid XML"):
        asyncio.run(
            WeWorkRemotelyCollector(
                base_url="https://wwr.test",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, content=b"<rss>", request=request)
                ),
            ).collect()
        )

    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(
            WeWorkRemotelyCollector(
                base_url="https://wwr.test",
                transport=httpx.MockTransport(network_failure),
            ).collect()
        )
