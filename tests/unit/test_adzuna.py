"""Tests for the Adzuna collector and normalizer."""

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from job_market_analyzer.collectors.adzuna import (
    ADZUNA_SOURCE_PROVIDER,
    AdzunaAPIError,
    collect_adzuna_jobs,
)
from job_market_analyzer.models import EmploymentType, RawJob, SalaryPeriod
from job_market_analyzer.normalization.adzuna import (
    AdzunaNormalizationError,
    normalize_adzuna_job,
)

FETCHED_AT = datetime(2026, 8, 23, 22, 0, tzinfo=UTC)
APP_ID = "testappid"
APP_KEY = "testappkey"


def _job(identifier: int) -> dict[str, object]:
    return {
        "id": identifier,
        "title": "Senior Python Developer",
        "description": "Build remote APIs. Django, REST.",
        "redirect_url": f"https://www.adzuna.co.uk/jobs/land/ad/{identifier}",
        "company": {"display_name": "Acme Ltd"},
        "location": {"display_name": "London"},
        "created": "2026-08-20T12:00:00Z",
        "contract_type": "contract",
        "category": {"tag": "it-jobs", "label": "IT Jobs"},
        "salary_is_predicted": "0",
        "salary_min": 93600,
        "salary_max": 104000,
    }


def _search(jobs: list[dict[str, object]]) -> dict[str, object]:
    return {"count": len(jobs), "results": jobs}


def test_collects_countries_with_credentials_in_params() -> None:
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                str(request.url.params["app_id"]),
                str(request.url.params["app_key"]),
                request.url.path,
            )
        )
        return httpx.Response(200, json=_search([_job(1)]), request=request)

    result = asyncio.run(
        collect_adzuna_jobs(
            base_url="https://adzuna.test",
            app_id=APP_ID,
            app_key=APP_KEY,
            countries=("gb", "us"),
            max_pages=1,
            results_per_page=10,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert all(s[0] == APP_ID and s[1] == APP_KEY for s in seen)
    assert any("/gb/search/1" in s[2] for s in seen)
    assert any("/us/search/1" in s[2] for s in seen)
    assert result.fetched == 2
    assert result.failures == ()
    scopes = {job.source_scope for job in result.jobs}
    assert scopes == {"gb", "us"}


def test_country_failure_is_isolated_later_country_continues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in request.url.path:
            return httpx.Response(500, request=request)
        return httpx.Response(200, json=_search([_job(5)]), request=request)

    result = asyncio.run(
        collect_adzuna_jobs(
            base_url="https://adzuna.test",
            app_id=APP_ID,
            app_key=APP_KEY,
            countries=("broken", "healthy"),
            max_pages=1,
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 1
    assert len(result.failures) == 1
    assert result.failures[0].external_id == "broken"
    assert result.metadata["countries_failed"] == 1


def test_all_countries_failing_is_systemic() -> None:
    with pytest.raises(AdzunaAPIError):
        asyncio.run(
            collect_adzuna_jobs(
                base_url="https://adzuna.test",
                app_id=APP_ID,
                app_key=APP_KEY,
                countries=("one",),
                max_pages=1,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(503, request=request)
                ),
                clock=lambda: FETCHED_AT,
            )
        )


def test_empty_credentials_rejected() -> None:
    with pytest.raises(ValueError, match="app_id"):
        asyncio.run(
            collect_adzuna_jobs(
                base_url="https://adzuna.test",
                app_id="",
                app_key=APP_KEY,
                countries=("gb",),
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, request=request)
                ),
                clock=lambda: FETCHED_AT,
            )
        )


def _raw(payload: dict[str, object], external_id: str = "5832059894") -> RawJob:
    return RawJob(
        source_provider=ADZUNA_SOURCE_PROVIDER,
        source_scope="gb",
        external_id=external_id,
        source_url=None,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def _payload() -> dict[str, object]:
    return _job(5832059894)


def test_normalizes_adzuna_payload_with_structured_salary() -> None:
    posting = normalize_adzuna_job(_raw(_payload(), "5832059894"))

    from decimal import Decimal

    assert posting.source_provider == "adzuna"
    assert posting.title == "Senior Python Developer"
    assert posting.company_name == "Acme Ltd"
    assert posting.description_text == "Build remote APIs. Django, REST."
    assert posting.location_text == "London"
    assert posting.employment_type is EmploymentType.CONTRACT
    assert posting.salary_min == Decimal("93600")
    assert posting.salary_max == Decimal("104000")
    assert posting.salary_currency == "GBP"
    assert posting.salary_period is SalaryPeriod.YEARLY
    assert posting.source_tags == ("IT Jobs",)
    assert posting.published_at == datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    assert posting.source_url is not None


def test_predicted_salary_yields_no_salary_fields() -> None:
    payload = _payload()
    payload["salary_is_predicted"] = "1"
    posting = normalize_adzuna_job(_raw(payload, "5832059894"))
    assert posting.salary_min is None
    assert posting.salary_max is None
    assert posting.salary_currency is None


def test_identity_mismatch_rejected() -> None:
    with pytest.raises(AdzunaNormalizationError, match="identity"):
        normalize_adzuna_job(_raw(_payload(), "999"))


def test_wrong_provider_rejected() -> None:
    raw = RawJob(
        source_provider="greenhouse",
        source_scope="gb",
        external_id="1",
        source_url=None,
        fetched_at=FETCHED_AT,
        payload=_payload(),
    )
    with pytest.raises(AdzunaNormalizationError):
        normalize_adzuna_job(raw)
