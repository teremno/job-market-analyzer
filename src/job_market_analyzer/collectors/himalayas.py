"""Himalayas collector using its public paginated remote-jobs API."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.models import RawJob

HIMALAYAS_BASE_URL = "https://himalayas.app"
HIMALAYAS_ENDPOINT = "/jobs/api"
HIMALAYAS_SOURCE_PROVIDER = "himalayas"
HIMALAYAS_SOURCE_SCOPE = "global"
HIMALAYAS_USER_AGENT = "job-market-analyzer/0.1"


class HimalayasFeedError(ValueError):
    """Raised when Himalayas returns an unsupported jobs response."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class HimalayasCollector:
    """Collect a small bounded set of public Himalayas remote jobs."""

    def __init__(
        self,
        *,
        base_url: str = HIMALAYAS_BASE_URL,
        page_size: int = 20,
        max_pages: int = 3,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not 1 <= page_size <= 20:
            raise ValueError("Himalayas page_size must be between 1 and 20")
        if max_pages < 1:
            raise ValueError("Himalayas max_pages must be greater than zero")
        self._base_url = base_url.rstrip("/")
        self._page_size = page_size
        self._max_pages = max_pages
        self._timeout = timeout
        self._transport = transport
        self._clock = clock

    async def collect(self) -> CollectedJobs:
        """Fetch bounded pages and report malformed individual jobs."""

        feed_items: list[object] = []
        metadata: dict[str, object] = {}
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Accept": "application/json",
                "User-Agent": HIMALAYAS_USER_AGENT,
            },
            timeout=httpx.Timeout(self._timeout),
            transport=self._transport,
        ) as client:
            for page_index in range(self._max_pages):
                response = await client.get(
                    HIMALAYAS_ENDPOINT,
                    params={
                        "limit": self._page_size,
                        "offset": page_index * self._page_size,
                    },
                )
                response.raise_for_status()
                page_items, page_metadata = _parse_page(response)
                feed_items.extend(page_items)
                metadata = page_metadata
                if len(page_items) < self._page_size:
                    break

        fetched_at = self._clock()
        _require_aware_clock(fetched_at, "HimalayasCollector")
        jobs: list[RawJob] = []
        failures: list[CollectionFailure] = []
        seen_external_ids: set[str] = set()
        duplicates_skipped = 0
        for item_index, item in enumerate(feed_items):
            try:
                job = _to_raw_job(item, fetched_at=fetched_at)
                if job.external_id in seen_external_ids:
                    duplicates_skipped += 1
                    continue
                seen_external_ids.add(job.external_id)
                jobs.append(job)
            except (TypeError, ValueError) as exc:
                failures.append(
                    CollectionFailure(
                        source_provider=HIMALAYAS_SOURCE_PROVIDER,
                        stage="collect",
                        message=str(exc),
                        item_index=item_index,
                        external_id=_failure_external_id(item, "guid"),
                    )
                )
        if duplicates_skipped:
            metadata = {**metadata, "duplicates_skipped": duplicates_skipped}
        return CollectedJobs(
            fetched=len(feed_items),
            jobs=tuple(jobs),
            failures=tuple(failures),
            metadata=metadata or None,
        )


def _parse_page(response: httpx.Response) -> tuple[list[object], dict[str, object]]:
    try:
        feed = response.json()
    except ValueError as exc:
        raise HimalayasFeedError("Himalayas returned invalid JSON") from exc
    if not isinstance(feed, dict) or not isinstance(feed.get("jobs"), list):
        raise HimalayasFeedError("Himalayas response must contain a jobs array")
    return feed["jobs"], {key: value for key, value in feed.items() if key != "jobs"}


def _to_raw_job(item: object, *, fetched_at: datetime) -> RawJob:
    if not isinstance(item, dict):
        raise TypeError("Himalayas job entry must be a JSON object")
    guid = _required_text(item.get("guid"), "guid")
    return RawJob(
        source_provider=HIMALAYAS_SOURCE_PROVIDER,
        source_scope=HIMALAYAS_SOURCE_SCOPE,
        external_id=guid,
        source_url=guid,
        fetched_at=fetched_at,
        payload=item,
    )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Himalayas job field '{field_name}' must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"Himalayas job field '{field_name}' must not be blank")
    return text


def _failure_external_id(item: object, field_name: str) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get(field_name)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _require_aware_clock(value: datetime, collector_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{collector_name} clock must return an aware datetime")
