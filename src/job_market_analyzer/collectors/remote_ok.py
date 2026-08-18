"""Remote OK collector using the official public JSON feed."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import (
    CollectedJobs,
    CollectionFailure,
)
from job_market_analyzer.models import RawJob

REMOTE_OK_BASE_URL = "https://remoteok.com"
REMOTE_OK_ENDPOINT = "/api"
REMOTE_OK_SOURCE_PROVIDER = "remote_ok"
REMOTE_OK_SOURCE_SCOPE = "global"
REMOTE_OK_USER_AGENT = "job-market-analyzer/0.1"


class RemoteOKFeedError(ValueError):
    """Raised when the Remote OK response is not a supported feed."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RemoteOKCollector:
    """Collect source-native Remote OK jobs without scraping HTML pages."""

    def __init__(
        self,
        *,
        base_url: str = REMOTE_OK_BASE_URL,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._clock = clock

    async def collect(self) -> CollectedJobs:
        """Fetch one feed; keep valid jobs and report malformed items explicitly."""

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Accept": "application/json",
                "User-Agent": REMOTE_OK_USER_AGENT,
            },
            timeout=httpx.Timeout(self._timeout),
            transport=self._transport,
        ) as client:
            response = await client.get(REMOTE_OK_ENDPOINT)
            response.raise_for_status()

        try:
            feed = response.json()
        except ValueError as exc:
            raise RemoteOKFeedError("Remote OK returned invalid JSON") from exc

        if not isinstance(feed, list):
            raise RemoteOKFeedError("Remote OK feed must be a JSON array")

        fetched_at = self._clock()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("RemoteOKCollector clock must return an aware datetime")

        jobs: list[RawJob] = []
        failures: list[CollectionFailure] = []
        metadata: dict[str, object] | None = None
        fetched = 0

        for item_index, item in enumerate(feed):
            if self._is_metadata_header(item_index, item):
                metadata = dict(item)
                continue

            fetched += 1
            try:
                jobs.append(self._to_raw_job(item, fetched_at=fetched_at))
            except (TypeError, ValueError) as exc:
                failures.append(
                    CollectionFailure(
                        source_provider=REMOTE_OK_SOURCE_PROVIDER,
                        stage="collect",
                        message=str(exc),
                        item_index=item_index,
                        external_id=self._failure_external_id(item),
                    )
                )

        return CollectedJobs(
            fetched=fetched,
            jobs=tuple(jobs),
            failures=tuple(failures),
            metadata=metadata,
        )

    @staticmethod
    def _is_metadata_header(item_index: int, item: object) -> bool:
        return (
            item_index == 0
            and isinstance(item, dict)
            and "id" not in item
            and ("legal" in item or "last_updated" in item)
        )

    @staticmethod
    def _to_raw_job(item: object, *, fetched_at: datetime) -> RawJob:
        if not isinstance(item, dict):
            raise TypeError("Remote OK job entry must be a JSON object")

        external_id = _required_source_id(item.get("id"))
        source_url = _required_text(item.get("url"), field_name="url")

        return RawJob(
            source_provider=REMOTE_OK_SOURCE_PROVIDER,
            source_scope=REMOTE_OK_SOURCE_SCOPE,
            external_id=external_id,
            source_url=source_url,
            fetched_at=fetched_at,
            payload=item,
        )

    @staticmethod
    def _failure_external_id(item: object) -> str | None:
        if not isinstance(item, dict):
            return None

        value = item.get("id")
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            return None

        external_id = str(value).strip()
        return external_id or None


def _required_source_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("Remote OK job field 'id' must be a string or integer")

    external_id = str(value).strip()
    if not external_id:
        raise ValueError("Remote OK job field 'id' must not be blank")

    return external_id


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Remote OK job field '{field_name}' must be a string")

    text = value.strip()
    if not text:
        raise ValueError(f"Remote OK job field '{field_name}' must not be blank")

    return text
