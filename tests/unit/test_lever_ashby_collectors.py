import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.ashby import (
    ASHBY_BOARD_TOKENS,
    AshbyAPIError,
    collect_ashby_boards,
)
from job_market_analyzer.collectors.lever import (
    LEVER_BOARD_TOKENS,
    LeverAPIError,
    collect_lever_boards,
)

FETCHED_AT = datetime(2026, 8, 22, 14, 0, tzinfo=UTC)


def _lever_job(identifier: str) -> dict[str, object]:
    return {
        "id": identifier,
        "text": "Backend Engineer",
        "hostedUrl": f"https://jobs.lever.co/test/{identifier}",
        "applyUrl": f"https://jobs.lever.co/test/{identifier}/apply",
        "createdAt": 1755000000000,
        "workplaceType": "remote",
        "categories": {"location": "Remote - EMEA", "commitment": "Permanent"},
        "descriptionPlain": "Build APIs.",
    }


def _ashby_job(identifier: str) -> dict[str, object]:
    return {
        "id": identifier,
        "title": "Senior Backend Engineer",
        "jobUrl": f"https://jobs.ashbyhq.com/test/{identifier}",
        "applyUrl": f"https://jobs.ashbyhq.com/test/{identifier}/application",
        "publishedAt": "2026-08-01T10:00:00.000+00:00",
        "isRemote": True,
        "employmentType": "FullTime",
        "location": "Europe",
        "department": "Engineering",
        "team": "Platform",
        "descriptionPlain": "Build things.",
    }


def _respond_array(jobs: list[dict[str, object]], request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=jobs, request=request)


def test_lever_collects_all_boards_with_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mode"] == "json"
        return _respond_array([_lever_job("a"), _lever_job("b")], request)

    result = asyncio.run(
        collect_lever_boards(
            base_url="https://lever.test",
            board_tokens=("one", "two"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 4
    scopes = {(job.source_scope, job.external_id) for job in result.jobs}
    assert ("one", "a") in scopes
    assert ("two", "b") in scopes
    assert result.failures == ()
    assert result.metadata["boards_collected"] == 2


def test_ashby_collects_all_boards_with_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["includeCompensation"] == "true"
        return httpx.Response(
            200,
            json={"jobs": [_ashby_job("x"), _ashby_job("y")]},
            request=request,
        )

    result = asyncio.run(
        collect_ashby_boards(
            base_url="https://ashby.test",
            board_tokens=("one", "two"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 4
    scopes = {(job.source_scope, job.external_id) for job in result.jobs}
    assert ("two", "y") in scopes


@pytest.mark.parametrize(
    ("collector", "board_response"),
    [
        (
            collect_lever_boards,
            lambda request: httpx.Response(500, request=request),
        ),
        (
            collect_ashby_boards,
            lambda request: httpx.Response(404, request=request),
        ),
    ],
)
def test_board_failure_is_isolated(collector, board_response) -> None:
    if collector is collect_lever_boards:
        healthy = lambda request: _respond_array([_lever_job("1")], request)  # noqa: E731
    else:
        healthy = lambda request: httpx.Response(  # noqa: E731
            200, json={"jobs": [_ashby_job("1")]}, request=request
        )

    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in request.url.path:
            return board_response(request)
        return healthy(request)

    result = asyncio.run(
        collector(
            base_url="https://test",
            board_tokens=("broken", "healthy"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 1
    assert len(result.failures) == 1
    assert result.failures[0].external_id == "broken"


@pytest.mark.parametrize("collector", [collect_lever_boards, collect_ashby_boards])
def test_every_board_failing_is_systemic(collector) -> None:
    with pytest.raises((LeverAPIError, AshbyAPIError)):
        asyncio.run(
            collector(
                base_url="https://test",
                board_tokens=("one",),
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(503, request=request)
                ),
                clock=lambda: FETCHED_AT,
            )
        )


def test_curated_registrations_are_lowercase_and_bounded() -> None:
    assert len(LEVER_BOARD_TOKENS) == 2
    assert len(ASHBY_BOARD_TOKENS) == 21
    from job_market_analyzer.collectors.greenhouse import GREENHOUSE_BOARD_TOKENS

    assert len(GREENHOUSE_BOARD_TOKENS) == 22
    for tokens in (LEVER_BOARD_TOKENS, ASHBY_BOARD_TOKENS, GREENHOUSE_BOARD_TOKENS):
        assert all(token == token.strip().lower() for token in tokens)
