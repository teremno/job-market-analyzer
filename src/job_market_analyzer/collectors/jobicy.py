"""Jobicy collector using its public remote-jobs API."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.models import RawJob

JOBICY_BASE_URL = "https://jobicy.com"
JOBICY_ENDPOINT = "/api/v2/remote-jobs"
JOBICY_SOURCE_PROVIDER = "jobicy"
JOBICY_SOURCE_SCOPE = "global"
JOBICY_USER_AGENT = "job-market-analyzer/0.1"


class JobicyFeedError(ValueError):
    """Raised when Jobicy returns an unsupported jobs response."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JobicyCollector:
    """Collect one bounded public Jobicy remote-jobs response."""

    def __init__(
        self,
        *,
        base_url: str = JOBICY_BASE_URL,
        count: int = 50,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not 1 <= count <= 100:
            raise ValueError("Jobicy count must be between 1 and 100")
        self._base_url = base_url.rstrip("/")
        self._count = count
        self._timeout = timeout
        self._transport = transport
        self._clock = clock

    async def collect(self) -> CollectedJobs:
        """Fetch one feed and keep valid jobs when individual items are malformed."""

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Accept": "application/json", "User-Agent": JOBICY_USER_AGENT},
            timeout=httpx.Timeout(self._timeout),
            transport=self._transport,
        ) as client:
            response = await client.get(JOBICY_ENDPOINT, params={"count": self._count})
            response.raise_for_status()
        try:
            feed = response.json()
        except ValueError as exc:
            raise JobicyFeedError("Jobicy returned invalid JSON") from exc
        if not isinstance(feed, dict) or not isinstance(feed.get("jobs"), list):
            raise JobicyFeedError("Jobicy response must contain a jobs array")

        fetched_at = self._clock()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("JobicyCollector clock must return an aware datetime")
        feed_items = feed["jobs"]
        jobs: list[RawJob] = []
        failures: list[CollectionFailure] = []
        for item_index, item in enumerate(feed_items):
            try:
                jobs.append(_to_raw_job(item, fetched_at=fetched_at))
            except (TypeError, ValueError) as exc:
                failures.append(
                    CollectionFailure(
                        source_provider=JOBICY_SOURCE_PROVIDER,
                        stage="collect",
                        message=str(exc),
                        item_index=item_index,
                        external_id=_failure_external_id(item),
                    )
                )
        metadata = {key: value for key, value in feed.items() if key != "jobs"}
        return CollectedJobs(
            fetched=len(feed_items),
            jobs=tuple(jobs),
            failures=tuple(failures),
            metadata=metadata or None,
        )


def _to_raw_job(item: object, *, fetched_at: datetime) -> RawJob:
    if not isinstance(item, dict):
        raise TypeError("Jobicy job entry must be a JSON object")
    external_id = _required_id(item.get("id"))
    source_url = _required_text(item.get("url"), "url")
    return RawJob(
        source_provider=JOBICY_SOURCE_PROVIDER,
        source_scope=JOBICY_SOURCE_SCOPE,
        external_id=external_id,
        source_url=source_url,
        fetched_at=fetched_at,
        payload=item,
    )


def _required_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("Jobicy job field 'id' must be a string or integer")
    external_id = str(value).strip()
    if not external_id:
        raise ValueError("Jobicy job field 'id' must not be blank")
    return external_id


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Jobicy job field '{field_name}' must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"Jobicy job field '{field_name}' must not be blank")
    return text


def _failure_external_id(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return str(value).strip() or None
