"""Lever collector using the official credential-free postings API."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.models import RawJob

LEVER_BASE_URL = "https://api.lever.co"
LEVER_SOURCE_PROVIDER = "lever"
LEVER_USER_AGENT = "job-market-analyzer/0.1"

# Curated public Lever boards approved for the pilot (documented in
# docs/SOURCES.md). Each token is one company's public postings feed.
LEVER_BOARD_TOKENS: tuple[str, ...] = (
    "spotify",
    "palantir",
)


class LeverFeedError(ValueError):
    """Raised when a Lever board returns an unsupported postings response."""


class LeverAPIError(RuntimeError):
    """Raised when every configured Lever board fails."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def collect_lever_boards(
    *,
    base_url: str = LEVER_BASE_URL,
    board_tokens: tuple[str, ...] = LEVER_BOARD_TOKENS,
    timeout: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> CollectedJobs:
    """Fetch one response per board and report per-board failures.

    A failed board is an isolated result while later boards continue. Only an
    empty board-token list or failures on every board are systemic errors.
    """

    if not board_tokens:
        raise ValueError("At least one Lever board token is required")

    fetched_at = clock()
    _require_aware_clock(fetched_at)

    jobs: list[RawJob] = []
    failures: list[CollectionFailure] = []
    metadata: dict[str, object] = {"boards_requested": len(board_tokens)}
    boards_ok = 0
    boards_failed = 0
    seen_ids: set[tuple[str, str]] = set()
    duplicates_skipped = 0

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Accept": "application/json",
            "User-Agent": LEVER_USER_AGENT,
        },
        timeout=httpx.Timeout(timeout),
        transport=transport,
    ) as client:
        for token in board_tokens:
            try:
                response = await client.get(
                    f"/v0/postings/{token}",
                    params={"mode": "json"},
                )
                response.raise_for_status()
                board_jobs = _parse_board(response, token)
            except httpx.HTTPError as exc:
                failures.append(_board_failure(token, f"HTTP failure: {type(exc).__name__}"))
                boards_failed += 1
                continue
            except LeverFeedError as exc:
                failures.append(_board_failure(token, str(exc)))
                boards_failed += 1
                continue

            boards_ok += 1
            for item_index, item in enumerate(board_jobs):
                try:
                    job = _to_raw_job(item, source_scope=token, fetched_at=fetched_at)
                except (TypeError, ValueError) as exc:
                    failures.append(
                        CollectionFailure(
                            source_provider=LEVER_SOURCE_PROVIDER,
                            stage="collect",
                            message=str(exc),
                            item_index=item_index,
                            external_id=_failure_external_id(item),
                        )
                    )
                    continue
                identity = (job.source_scope, job.external_id)
                if identity in seen_ids:
                    duplicates_skipped += 1
                    continue
                seen_ids.add(identity)
                jobs.append(job)

    if boards_ok == 0:
        raise LeverAPIError("Every configured Lever board request failed")

    if duplicates_skipped:
        metadata["duplicates_skipped"] = duplicates_skipped
    metadata["boards_collected"] = boards_ok
    metadata["boards_failed"] = boards_failed
    return CollectedJobs(
        fetched=len(jobs),
        jobs=tuple(jobs),
        failures=tuple(failures),
        metadata=metadata,
    )


class LeverCollector:
    """Collector adapter collecting all curated Lever boards in one run."""

    def __init__(
        self,
        *,
        base_url: str = LEVER_BASE_URL,
        board_tokens: tuple[str, ...] = LEVER_BOARD_TOKENS,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._options = {
            "base_url": base_url,
            "board_tokens": board_tokens,
            "timeout": timeout,
            "transport": transport,
            "clock": clock,
        }

    async def collect(self) -> CollectedJobs:
        """Fetch one bounded response per curated board."""

        return await collect_lever_boards(**self._options)


def _parse_board(response: httpx.Response, token: str) -> list[object]:
    try:
        feed = response.json()
    except ValueError as exc:
        raise LeverFeedError(f"Board '{token}' returned invalid JSON") from exc
    if not isinstance(feed, list):
        raise LeverFeedError(f"Board '{token}' response must be a JSON array")
    return feed


def _to_raw_job(
    item: object, *, source_scope: str, fetched_at: datetime
) -> RawJob:
    if not isinstance(item, dict):
        raise TypeError("Lever posting entry must be a JSON object")
    external_id = _required_text(item.get("id"), "id")
    source_url = _optional_text(item.get("hostedUrl"), "hostedUrl")
    return RawJob(
        source_provider=LEVER_SOURCE_PROVIDER,
        source_scope=source_scope,
        external_id=external_id,
        source_url=source_url,
        fetched_at=fetched_at,
        payload=item,
    )


def _board_failure(token: str, message: str) -> CollectionFailure:
    return CollectionFailure(
        source_provider=LEVER_SOURCE_PROVIDER,
        stage="collect",
        message=f"board '{token}': {message}",
        external_id=token,
    )


def _required_text(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError(f"Lever field '{field_name}' must be a string or integer")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Lever field '{field_name}' must not be blank")
    return text


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Lever field '{field_name}' must be a string")
    text = value.strip()
    return text or None


def _failure_external_id(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text or None


def _require_aware_clock(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("LeverCollector clock must return an aware datetime")
