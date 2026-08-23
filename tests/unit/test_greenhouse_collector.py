import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.greenhouse import (
    GREENHOUSE_BOARD_TOKENS,
    GreenhouseAPIError,
    collect_greenhouse_boards,
)

FETCHED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _job_payload(identifier: int) -> dict[str, object]:
    return {
        "id": identifier,
        "title": f"Engineer {identifier}",
        "absolute_url": f"https://boards.greenhouse.io/test/jobs/{identifier}",
        "content": "<p>Build things.</p>",
        "first_published": "2026-08-01T10:00:00-04:00",
        "updated_at": "2026-08-20T09:00:00-04:00",
        "location": {"name": "Remote (Europe)"},
    }


def _board_response(
    jobs: list[dict[str, object]], request: httpx.Request
) -> httpx.Response:
    return httpx.Response(200, json={"jobs": jobs, "meta": {}}, request=request)


def test_collects_all_boards_with_content_and_identity() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        assert request.url.params["content"] == "true"
        return _board_response([_job_payload(1), _job_payload(2)], request)

    result = asyncio.run(
        collect_greenhouse_boards(
            base_url="https://greenhouse.test",
            board_tokens=("alpha", "beta"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert requested_paths == [
        "/v1/boards/alpha/jobs",
        "/v1/boards/beta/jobs",
    ]
    assert result.fetched == 4
    scopes = {(job.source_scope, job.external_id) for job in result.jobs}
    assert scopes == {
        ("alpha", "1"),
        ("alpha", "2"),
        ("beta", "1"),
        ("beta", "2"),
    }
    assert result.failures == ()
    assert result.metadata == {
        "boards_requested": 2,
        "boards_collected": 2,
        "boards_failed": 0,
    }


def test_board_failure_is_isolated_and_later_boards_continue() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in request.url.path:
            return httpx.Response(500, request=request)
        return _board_response([_job_payload(7)], request)

    result = asyncio.run(
        collect_greenhouse_boards(
            base_url="https://greenhouse.test",
            board_tokens=("broken", "healthy"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 1
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.external_id == "broken"
    assert failure.stage == "collect"
    assert result.metadata["boards_collected"] == 1
    assert result.metadata["boards_failed"] == 1


def test_invalid_json_on_one_board_does_not_stop_other_boards() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "badshape" in request.url.path:
            return httpx.Response(200, json={"unexpected": True}, request=request)
        return _board_response([_job_payload(3)], request)

    result = asyncio.run(
        collect_greenhouse_boards(
            base_url="https://greenhouse.test",
            board_tokens=("badshape", "good"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert [job.source_scope for job in result.jobs] == ["good"]
    assert len(result.failures) == 1


def test_malformed_item_becomes_failure_valid_job_continues() -> None:
    payload = _job_payload(9)

    def handler(request: httpx.Request) -> httpx.Response:
        return _board_response([{"title": "missing id"}, payload], request)

    result = asyncio.run(
        collect_greenhouse_boards(
            base_url="https://greenhouse.test",
            board_tokens=("only",),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert [job.external_id for job in result.jobs] == ["9"]
    assert len(result.failures) == 1
    assert result.failures[0].item_index == 0


def test_every_board_failing_is_systemic() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    with pytest.raises(GreenhouseAPIError):
        asyncio.run(
            collect_greenhouse_boards(
                base_url="https://greenhouse.test",
                board_tokens=("one", "two"),
                transport=httpx.MockTransport(handler),
                clock=lambda: FETCHED_AT,
            )
        )


def test_duplicate_identity_within_source_is_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _board_response([_job_payload(5), _job_payload(5)], request)

    result = asyncio.run(
        collect_greenhouse_boards(
            base_url="https://greenhouse.test",
            board_tokens=("dupe",),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 1
    assert result.metadata["duplicates_skipped"] == 1


def test_empty_token_list_rejected() -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            collect_greenhouse_boards(
                base_url="https://greenhouse.test",
                board_tokens=(),
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, request=request)
                ),
                clock=lambda: FETCHED_AT,
            )
        )


def test_curated_board_registry_matches_approved_pilot() -> None:
    assert len(GREENHOUSE_BOARD_TOKENS) == 25
    assert "coinbase" in GREENHOUSE_BOARD_TOKENS
    assert "recordedfuture" in GREENHOUSE_BOARD_TOKENS
    assert all(token == token.strip().lower() for token in GREENHOUSE_BOARD_TOKENS)
