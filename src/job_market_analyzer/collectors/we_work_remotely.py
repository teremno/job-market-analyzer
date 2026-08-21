"""We Work Remotely collector using its official public RSS feed."""

import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.models import RawJob

WE_WORK_REMOTELY_BASE_URL = "https://weworkremotely.com"
WE_WORK_REMOTELY_ENDPOINT = "/remote-jobs.rss"
WE_WORK_REMOTELY_SOURCE_PROVIDER = "we_work_remotely"
WE_WORK_REMOTELY_SOURCE_SCOPE = "global"
WE_WORK_REMOTELY_USER_AGENT = "job-market-analyzer/0.1"


class WeWorkRemotelyFeedError(ValueError):
    """Raised when the We Work Remotely RSS document is invalid."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WeWorkRemotelyCollector:
    """Collect the official WWR RSS without scraping job pages."""

    def __init__(
        self,
        *,
        base_url: str = WE_WORK_REMOTELY_BASE_URL,
        limit: int = 100,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if limit < 1:
            raise ValueError("We Work Remotely limit must be greater than zero")
        self._base_url = base_url.rstrip("/")
        self._limit = limit
        self._timeout = timeout
        self._transport = transport
        self._clock = clock

    async def collect(self) -> CollectedJobs:
        """Fetch one RSS document and report malformed individual items."""

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Accept": "application/rss+xml, application/xml",
                "User-Agent": WE_WORK_REMOTELY_USER_AGENT,
            },
            timeout=httpx.Timeout(self._timeout),
            transport=self._transport,
        ) as client:
            response = await client.get(WE_WORK_REMOTELY_ENDPOINT)
            response.raise_for_status()
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise WeWorkRemotelyFeedError(
                "We Work Remotely returned invalid XML"
            ) from exc
        items = root.findall("./channel/item")
        if root.tag != "rss" or root.find("./channel") is None:
            raise WeWorkRemotelyFeedError(
                "We Work Remotely feed must contain an RSS channel"
            )
        items = items[: self._limit]
        fetched_at = self._clock()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError(
                "WeWorkRemotelyCollector clock must return an aware datetime"
            )

        jobs: list[RawJob] = []
        failures: list[CollectionFailure] = []
        seen_external_ids: set[str] = set()
        duplicates_skipped = 0
        for item_index, item in enumerate(items):
            payload = {_local_name(child.tag): child.text for child in item}
            try:
                job = _to_raw_job(payload, fetched_at=fetched_at)
                if job.external_id in seen_external_ids:
                    duplicates_skipped += 1
                    continue
                seen_external_ids.add(job.external_id)
                jobs.append(job)
            except (TypeError, ValueError) as exc:
                failures.append(
                    CollectionFailure(
                        source_provider=WE_WORK_REMOTELY_SOURCE_PROVIDER,
                        stage="collect",
                        message=str(exc),
                        item_index=item_index,
                        external_id=_failure_external_id(payload),
                    )
                )
        return CollectedJobs(
            fetched=len(items),
            jobs=tuple(jobs),
            failures=tuple(failures),
            metadata=(
                {"duplicates_skipped": duplicates_skipped}
                if duplicates_skipped
                else None
            ),
        )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _to_raw_job(payload: dict[str, object], *, fetched_at: datetime) -> RawJob:
    external_id = _required_text(payload.get("guid"), "guid")
    source_url = _required_text(payload.get("link"), "link")
    return RawJob(
        source_provider=WE_WORK_REMOTELY_SOURCE_PROVIDER,
        source_scope=WE_WORK_REMOTELY_SOURCE_SCOPE,
        external_id=external_id,
        source_url=source_url,
        fetched_at=fetched_at,
        payload=payload,
    )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"We Work Remotely job field '{field_name}' must be a string"
        )
    text = value.strip()
    if not text:
        raise ValueError(
            f"We Work Remotely job field '{field_name}' must not be blank"
        )
    return text


def _failure_external_id(payload: dict[str, object]) -> str | None:
    value = payload.get("guid")
    return value.strip() if isinstance(value, str) and value.strip() else None
