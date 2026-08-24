"""Adzuna collector using the official app_id/app_key search API."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from job_market_analyzer.collectors.base import CollectedJobs, CollectionFailure
from job_market_analyzer.models import RawJob

ADZUNA_BASE_URL = "https://api.adzuna.com"
ADZUNA_SOURCE_PROVIDER = "adzuna"
ADZUNA_USER_AGENT = "job-market-analyzer/0.1"

# Country scopes queried per run (Adzuna is country-partitioned).
ADZUNA_COUNTRIES: tuple[str, ...] = ("gb", "us")
ADZUNA_MAX_PAGES = 2
ADZUNA_RESULTS_PER_PAGE = 50

# Salaries are returned in the country's local currency.
COUNTRY_CURRENCY = {"gb": "GBP", "us": "USD"}


class AdzunaFeedError(ValueError):
    """Raised when Adzuna returns an unsupported search response."""


class AdzunaAPIError(RuntimeError):
    """Raised when every Adzuna country search fails."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def collect_adzuna_jobs(
    *,
    base_url: str = ADZUNA_BASE_URL,
    app_id: str,
    app_key: str,
    countries: tuple[str, ...] = ADZUNA_COUNTRIES,
    max_pages: int = ADZUNA_MAX_PAGES,
    results_per_page: int = ADZUNA_RESULTS_PER_PAGE,
    timeout: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> CollectedJobs:
    """Fetch bounded remote-search pages per country; report item failures.

    A failed country is an isolated result while later countries continue.
    All countries failing is a systemic error.
    """

    if not app_id.strip() or not app_key.strip():
        raise ValueError("Adzuna app_id and app_key are required")
    if not countries:
        raise ValueError("At least one Adzuna country is required")
    if max_pages < 1:
        raise ValueError("max_pages must be greater than zero")

    fetched_at = clock()
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError("AdzunaCollector clock must return an aware datetime")

    jobs: list[RawJob] = []
    failures: list[CollectionFailure] = []
    seen_ids: set[tuple[str, str]] = set()
    countries_ok = 0
    duplicates_skipped = 0

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Accept": "application/json",
            "User-Agent": ADZUNA_USER_AGENT,
        },
        timeout=httpx.Timeout(timeout),
        transport=transport,
    ) as client:
        for country in countries:
            for page in range(1, max_pages + 1):
                try:
                    response = await client.get(
                        f"/v1/api/jobs/{country}/search/{page}",
                        params={
                            "app_id": app_id,
                            "app_key": app_key,
                            "results_per_page": str(results_per_page),
                            "what": "remote",
                            "max_days_old": "30",
                        },
                    )
                    response.raise_for_status()
                    page_items = _parse_search(response, country)
                except httpx.HTTPError as exc:
                    failures.append(_country_failure(country, f"HTTP failure: {type(exc).__name__}"))
                    break
                except AdzunaFeedError as exc:
                    failures.append(_country_failure(country, str(exc)))
                    break

                countries_ok += 1
                any_items = False
                for item_index, item in enumerate(page_items):
                    any_items = True
                    try:
                        job = _to_raw_job(item, source_scope=country, fetched_at=fetched_at)
                    except (TypeError, ValueError) as exc:
                        failures.append(
                            CollectionFailure(
                                source_provider=ADZUNA_SOURCE_PROVIDER,
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
                if not any_items:
                    break

    if countries_ok == 0:
        raise AdzunaAPIError("Every Adzuna country search failed")

    metadata: dict[str, object] = {
        "countries_requested": len(countries),
        "countries_ok": countries_ok,
        "countries_failed": len(failures),
        "duplicates_skipped": duplicates_skipped,
    }
    return CollectedJobs(
        fetched=len(jobs),
        jobs=tuple(jobs),
        failures=tuple(failures),
        metadata=metadata,
    )


def _parse_search(response: httpx.Response, country: str) -> list[object]:
    try:
        feed = response.json()
    except ValueError as exc:
        raise AdzunaFeedError(f"Country '{country}' returned invalid JSON") from exc
    if not isinstance(feed, dict) or not isinstance(feed.get("results"), list):
        raise AdzunaFeedError(
            f"Country '{country}' response must contain a results array"
        )
    return feed["results"]


def _to_raw_job(item: object, *, source_scope: str, fetched_at: datetime) -> RawJob:
    if not isinstance(item, dict):
        raise TypeError("Adzuna job entry must be a JSON object")
    external_id = _required_text(item.get("id"), "id")
    redirect = _optional_text(item.get("redirect_url"), "redirect_url")
    return RawJob(
        source_provider=ADZUNA_SOURCE_PROVIDER,
        source_scope=source_scope,
        external_id=external_id,
        source_url=redirect,
        fetched_at=fetched_at,
        payload=item,
    )


def _country_failure(country: str, message: str) -> CollectionFailure:
    return CollectionFailure(
        source_provider=ADZUNA_SOURCE_PROVIDER,
        stage="collect",
        message=f"country '{country}': {message}",
        external_id=country,
    )


def _required_text(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError(f"Adzuna field '{field_name}' must be a string or integer")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Adzuna field '{field_name}' must not be blank")
    return text


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Adzuna field '{field_name}' must be a string")
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


class AdzunaCollector:
    """Collector adapter querying Adzuna remote searches per country."""

    def __init__(
        self,
        *,
        base_url: str = ADZUNA_BASE_URL,
        app_id: str | None = None,
        app_key: str | None = None,
        countries: tuple[str, ...] = ADZUNA_COUNTRIES,
        max_pages: int = ADZUNA_MAX_PAGES,
        results_per_page: int = ADZUNA_RESULTS_PER_PAGE,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        import os

        resolved_id = app_id if app_id is not None else os.getenv("ADZUNA_APP_ID")
        resolved_key = app_key if app_key is not None else os.getenv("ADZUNA_APP_KEY")
        if not resolved_id or not resolved_key:
            raise ValueError(
                "Adzuna credentials are required in ADZUNA_APP_ID and ADZUNA_APP_KEY"
            )
        self._options = {
            "base_url": base_url,
            "app_id": resolved_id,
            "app_key": resolved_key,
            "countries": countries,
            "max_pages": max_pages,
            "results_per_page": results_per_page,
            "timeout": timeout,
            "transport": transport,
            "clock": clock,
        }

    async def collect(self) -> CollectedJobs:
        """Fetch bounded remote-search pages per configured country."""

        return await collect_adzuna_jobs(**self._options)
