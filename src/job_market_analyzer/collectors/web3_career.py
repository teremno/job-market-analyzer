"""Web3.career collector using the official token-authenticated JSON API."""

import os
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.collectors.http import install_httpx_query_token_redaction
from job_market_analyzer.models import RawJob

WEB3_CAREER_BASE_URL = "https://web3.career/api"
WEB3_CAREER_ENDPOINT = "/v1"
WEB3_CAREER_SOURCE_PROVIDER = "web3_career"
WEB3_CAREER_SOURCE_SCOPE = "global"
WEB3_CAREER_TOKEN_ENV = "WEB3_CAREER_API_TOKEN"
WEB3_CAREER_USER_AGENT = "job-market-analyzer/0.1"


class Web3CareerConfigurationError(ValueError):
    """Raised when required Web3.career collector configuration is missing."""


class Web3CareerFeedError(ValueError):
    """Raised when Web3.career returns an unsupported JSON feed."""


class Web3CareerAPIError(RuntimeError):
    """Raised for a systemic Web3.career HTTP or network failure."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Web3CareerCollector:
    """Collect remote jobs from Web3.career without scraping listing pages."""

    def __init__(
        self,
        *,
        api_token: str | None = None,
        base_url: str = WEB3_CAREER_BASE_URL,
        endpoint: str = WEB3_CAREER_ENDPOINT,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        token = api_token if api_token is not None else os.getenv(WEB3_CAREER_TOKEN_ENV)
        if token is None or not token.strip():
            raise Web3CareerConfigurationError(
                f"Web3.career API token is required in {WEB3_CAREER_TOKEN_ENV}"
            )

        self._api_token = token.strip()
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint
        self._timeout = timeout
        self._transport = transport
        self._clock = clock

    async def collect(self) -> CollectedJobs:
        """Fetch one remote-only feed and report malformed individual jobs."""

        install_httpx_query_token_redaction()
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": WEB3_CAREER_USER_AGENT,
                },
                timeout=httpx.Timeout(self._timeout),
                transport=self._transport,
            ) as client:
                response = await client.get(
                    self._endpoint,
                    params={
                        "token": self._api_token,
                        "remote": "true",
                        "limit": 100,
                        "show_description": "true",
                    },
                )
        except httpx.RequestError as exc:
            raise Web3CareerAPIError(
                f"Web3.career request failed: {type(exc).__name__}"
            ) from None

        if not response.is_success:
            raise Web3CareerAPIError(
                f"Web3.career API returned HTTP {response.status_code}"
            )

        try:
            feed = response.json()
        except ValueError as exc:
            raise Web3CareerFeedError("Web3.career returned invalid JSON") from exc

        jobs_feed, metadata = _extract_jobs_feed(feed)
        fetched_at = self._clock()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("Web3CareerCollector clock must return an aware datetime")

        jobs: list[RawJob] = []
        failures: list[CollectionFailure] = []

        for item_index, item in enumerate(jobs_feed):
            try:
                jobs.append(self._to_raw_job(item, fetched_at=fetched_at))
            except (TypeError, ValueError) as exc:
                failures.append(
                    CollectionFailure(
                        source_provider=WEB3_CAREER_SOURCE_PROVIDER,
                        stage="collect",
                        message=str(exc),
                        item_index=item_index,
                        external_id=self._failure_external_id(item),
                    )
                )

        return CollectedJobs(
            fetched=len(jobs_feed),
            jobs=tuple(jobs),
            failures=tuple(failures),
            metadata=metadata,
        )

    @staticmethod
    def _to_raw_job(item: object, *, fetched_at: datetime) -> RawJob:
        if not isinstance(item, dict):
            raise TypeError("Web3.career job entry must be a JSON object")

        external_id = _required_source_id(item.get("id"))
        source_url = _required_text(item.get("url"), field_name="url")
        _required_text(item.get("apply_url"), field_name="apply_url")
        return RawJob(
            source_provider=WEB3_CAREER_SOURCE_PROVIDER,
            source_scope=WEB3_CAREER_SOURCE_SCOPE,
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


def _extract_jobs_feed(
    feed: object,
) -> tuple[list[object], dict[str, object] | None]:
    if not isinstance(feed, list):
        raise Web3CareerFeedError("Web3.career feed must be a JSON array")

    nested_jobs = next((item for item in feed if isinstance(item, list)), None)
    if nested_jobs is not None:
        metadata_items = [item for item in feed if not isinstance(item, list)]
        metadata = {"root_items": metadata_items} if metadata_items else None
        return nested_jobs, metadata

    if not feed:
        return [], None
    if all(isinstance(item, dict) for item in feed):
        return feed, None

    raise Web3CareerFeedError("Web3.career response does not contain a jobs array")


def _required_source_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("Web3.career job field 'id' must be a string or integer")

    external_id = str(value).strip()
    if not external_id:
        raise ValueError("Web3.career job field 'id' must not be blank")
    return external_id


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Web3.career job field '{field_name}' must be a string")

    text = value.strip()
    if not text:
        raise ValueError(f"Web3.career job field '{field_name}' must not be blank")
    return text
