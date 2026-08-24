"""Tests for The Muse collector and normalizer."""

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.the_muse import (
    THE_MUSE_SOURCE_PROVIDER,
    collect_the_muse_jobs,
)
from job_market_analyzer.models import RawJob
from job_market_analyzer.normalization.the_muse import (
    TheMuseNormalizationError,
    normalize_the_muse_job,
)

FETCHED_AT = datetime(2026, 8, 23, 20, 0, tzinfo=UTC)


def _job(identifier: int) -> dict[str, object]:
    return {
        "id": identifier,
        "name": "Backend Engineer",
        "company": {"short_name": "acme", "name": "Acme Corp"},
        "locations": [{"name": "Remote"}],
        "categories": [{"name": "Software Engineering"}],
        "levels": [{"name": "Senior Level", "short_name": "senior"}],
        "contents": "<p>Build APIs.</p>",
        "publication_date": "2026-08-20T12:00:00Z",
        "refs": {
            "landing_page": f"https://www.themuse.com/jobs/acme/{identifier}"
        },
        "type": "external",
    }


def _page(jobs: list[dict[str, object]], page: int, count: int) -> dict[str, object]:
    return {"page": page, "page_count": count, "results": jobs}


def test_collects_pages_stops_at_page_count_and_deduplicates() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.params["page"]))
        page = int(request.url.params["page"])
        jobs = [_job(1), _job(2)] if page == 1 else [_job(2)]
        return httpx.Response(
            200, json=_page(jobs, page, count=2), request=request
        )

    result = asyncio.run(
        collect_the_muse_jobs(
            base_url="https://muse.test",
            max_pages=3,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert calls == ["1", "2"]  # stopped because page >= page_count
    assert result.fetched == 2
    assert result.failures == ()
    assert result.metadata == {"pages_fetched": 2, "duplicates_skipped": 1}


def test_malformed_item_becomes_failure_valid_continues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_page([{"name": "no id"}, _job(9)], 1, count=1),
            request=request,
        )

    result = asyncio.run(
        collect_the_muse_jobs(
            base_url="https://muse.test",
            max_pages=1,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert [job.external_id for job in result.jobs] == ["9"]
    assert len(result.failures) == 1
    assert result.failures[0].item_index == 0


def test_page_error_is_systemic() -> None:
    with pytest.raises(Exception, match="page 1 request failed"):
        asyncio.run(
            collect_the_muse_jobs(
                base_url="https://muse.test",
                max_pages=1,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(500, request=request)
                ),
                clock=lambda: FETCHED_AT,
            )
        )


def _raw(payload: dict[str, object], external_id: str = "22038674") -> RawJob:
    return RawJob(
        source_provider=THE_MUSE_SOURCE_PROVIDER,
        source_scope="global",
        external_id=external_id,
        source_url=None,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def _payload() -> dict[str, object]:
    return _job(22038674)


def test_normalizes_muse_payload() -> None:
    posting = normalize_the_muse_job(_raw(_payload(), "22038674"))

    assert posting.source_provider == "the_muse"
    assert posting.title == "Backend Engineer"
    assert posting.company_name == "Acme Corp"
    assert posting.description_text == "Build APIs."
    assert posting.location_text == "Remote"
    assert posting.published_at == datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    assert posting.source_tags == ("Senior Level", "Software Engineering")
    assert posting.salary_text is None
    assert posting.is_remote is None
    assert posting.source_url is not None
    assert posting.application_url == posting.source_url


def test_identity_mismatch_rejected() -> None:
    with pytest.raises(TheMuseNormalizationError, match="identity"):
        normalize_the_muse_job(_raw(_payload(), "999"))


def test_naive_datetime_rejected() -> None:
    payload = _payload()
    payload["publication_date"] = "2026-08-20T12:00:00"
    with pytest.raises(TheMuseNormalizationError, match="timezone"):
        normalize_the_muse_job(_raw(payload, "22038674"))
