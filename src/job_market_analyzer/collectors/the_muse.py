"""The Muse collector using the public jobs API (key optional)."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.models import RawJob

THE_MUSE_BASE_URL = "https://www.themuse.com"
THE_MUSE_SOURCE_PROVIDER = "the_muse"
THE_MUSE_SOURCE_SCOPE = "global"
THE_MUSE_USER_AGENT = "job-market-analyzer/0.1"
THE_MUSE_TOKEN_ENV = "THE_MUSE_API_KEY"

# Bounded: three pages of 20 listings per run (public API, 20/page fixed).
THE_MUSE_MAX_PAGES = 3


class TheMuseFeedError(ValueError):
    """Raised when The Muse returns an unsupported jobs response."""


class TheMuseAPIError(RuntimeError):
    """Raised when every The Muse page request fails."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def collect_the_muse_jobs(
    *,
    base_url: str = THE_MUSE_BASE_URL,
    max_pages: int = THE_MUSE_MAX_PAGES,
    timeout: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], datetime] = _utc_now,
    api_key: str | None = None,
) -> CollectedJobs:
    """Fetch bounded pages of public listings and report malformed items."""

    if max_pages < 1:
        raise ValueError("max_pages must be greater than zero")

    fetched_at = clock()
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError("TheMuseCollector clock must return an aware datetime")

    jobs: list[RawJob] = []
    failures: list[CollectionFailure] = []
    seen_ids: set[str] = set()
    duplicates_skipped = 0
    last_page = 1

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Accept": "application/json",
            "User-Agent": THE_MUSE_USER_AGENT,
        },
        timeout=httpx.Timeout(timeout),
        transport=transport,
    ) as client:
        for page in range(1, max_pages + 1):
            params: dict[str, str] = {"page": str(page)}
            if api_key:
                params["api_key"] = api_key
            try:
                response = await client.get("/api/public/jobs", params=params)
                response.raise_for_status()
                page_items, page_count = _parse_page(response)
            except httpx.HTTPError as exc:
                raise TheMuseAPIError(
                    f"The Muse page {page} request failed: {type(exc).__name__}"
                ) from None
            except TheMuseFeedError:
                raise

            for item_index, item in enumerate(page_items):
                try:
                    job = _to_raw_job(item, fetched_at=fetched_at)
                except (TypeError, ValueError) as exc:
                    failures.append(
                        CollectionFailure(
                            source_provider=THE_MUSE_SOURCE_PROVIDER,
                            stage="collect",
                            message=str(exc),
                            item_index=item_index,
                            external_id=_failure_external_id(item),
                        )
                    )
                    continue
                if job.external_id in seen_ids:
                    duplicates_skipped += 1
                    continue
                seen_ids.add(job.external_id)
                jobs.append(job)

            last_page = page
            if page >= max(page_count, 1):
                break

    metadata: dict[str, object] = {
        "pages_fetched": last_page,
        "duplicates_skipped": duplicates_skipped,
    }
    return CollectedJobs(
        fetched=len(jobs),
        jobs=tuple(jobs),
        failures=tuple(failures),
        metadata=metadata,
    )


def _parse_page(response: httpx.Response) -> tuple[list[object], int]:
    try:
        feed = response.json()
    except ValueError as exc:
        raise TheMuseFeedError("The Muse returned invalid JSON") from exc
    if not isinstance(feed, dict) or not isinstance(feed.get("results"), list):
        raise TheMuseFeedError("The Muse response must contain a results array")
    page_count = feed.get("page_count")
    if isinstance(page_count, bool) or not isinstance(page_count, int) or page_count < 1:
        page_count = 1
    return feed["results"], page_count


def _to_raw_job(item: object, *, fetched_at: datetime) -> RawJob:
    if not isinstance(item, dict):
        raise TypeError("The Muse job entry must be a JSON object")
    external_id = _required_text(item.get("id"), "id")
    refs = item.get("refs")
    landing_page = None
    if isinstance(refs, dict) and isinstance(refs.get("landing_page"), str):
        landing_page = refs["landing_page"].strip() or None
    return RawJob(
        source_provider=THE_MUSE_SOURCE_PROVIDER,
        source_scope=THE_MUSE_SOURCE_SCOPE,
        external_id=external_id,
        source_url=landing_page,
        fetched_at=fetched_at,
        payload=item,
    )


def _required_text(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError(f"The Muse field '{field_name}' must be a string or integer")
    text = str(value).strip()
    if not text:
        raise ValueError(f"The Muse field '{field_name}' must not be blank")
    return text


def _failure_external_id(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text or None


class TheMuseCollector:
    """Collector adapter fetching bounded pages of The Muse public listings."""

    def __init__(
        self,
        *,
        base_url: str = THE_MUSE_BASE_URL,
        max_pages: int = THE_MUSE_MAX_PAGES,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
        api_key: str | None = None,
    ) -> None:
        self._options = {
            "base_url": base_url,
            "max_pages": max_pages,
            "timeout": timeout,
            "transport": transport,
            "clock": clock,
            "api_key": api_key,
        }

    async def collect(self) -> CollectedJobs:
        """Fetch bounded pages of The Muse public listings."""

        return await collect_the_muse_jobs(**self._options)
