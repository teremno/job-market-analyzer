from datetime import UTC, datetime

import pytest

from job_market_analyzer.collectors.ashby import ASHBY_SOURCE_PROVIDER
from job_market_analyzer.collectors.lever import LEVER_SOURCE_PROVIDER
from job_market_analyzer.models import EmploymentType, RawJob
from job_market_analyzer.normalization.ashby import (
    AshbyNormalizationError,
    normalize_ashby_job,
)
from job_market_analyzer.normalization.lever import (
    LeverNormalizationError,
    normalize_lever_job,
)

FETCHED_AT = datetime(2026, 8, 22, 14, 0, tzinfo=UTC)


def _raw(provider: str, payload: dict[str, object], external_id: str) -> RawJob:
    return RawJob(
        source_provider=provider,
        source_scope="test",
        external_id=external_id,
        source_url=None,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def _lever_payload() -> dict[str, object]:
    return {
        "id": "abc-123",
        "text": "Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/test/abc-123",
        "applyUrl": "https://jobs.lever.co/test/abc-123/apply",
        "createdAt": 1755000000000,
        "workplaceType": "remote",
        "categories": {
            "location": "Remote - EMEA",
            "commitment": "Permanent",
            "department": "Engineering",
            "team": "Platform",
        },
        "descriptionPlain": "Build APIs.\n\nShip services.",
    }


def _ashby_payload() -> dict[str, object]:
    return {
        "id": "xyz-9",
        "title": "Senior Fullstack Engineer",
        "jobUrl": "https://jobs.ashbyhq.com/test/xyz-9",
        "applyUrl": "https://jobs.ashbyhq.com/test/xyz-9/application",
        "publishedAt": "2026-08-01T10:00:00.000+00:00",
        "isRemote": True,
        "employmentType": "FullTime",
        "location": "Europe",
        "department": "Product",
        "team": "Engineering",
        "descriptionHtml": "<p>Build things.</p>",
    }


def test_normalizes_lever_payload() -> None:
    posting = normalize_lever_job(
        _raw(LEVER_SOURCE_PROVIDER, _lever_payload(), "abc-123")
    )

    assert posting.source_provider == "lever"
    assert posting.source_scope == "test"
    assert posting.title == "Backend Engineer"
    assert posting.company_name is None
    assert posting.description_text == "Build APIs.\n\nShip services."
    assert posting.location_text == "Remote - EMEA"
    assert posting.is_remote is True
    assert posting.remote_scope is None
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.salary_text is None
    assert posting.published_at == datetime(2025, 8, 12, 12, 0, tzinfo=UTC)
    assert posting.source_tags == ("Engineering", "Platform")
    assert posting.application_url is not None


def test_normalizes_ashby_payload_with_html_fallback() -> None:
    posting = normalize_ashby_job(
        _raw(ASHBY_SOURCE_PROVIDER, _ashby_payload(), "xyz-9")
    )

    assert posting.source_provider == "ashby"
    assert posting.title == "Senior Fullstack Engineer"
    assert posting.description_text == "Build things."
    assert posting.location_text == "Europe"
    assert posting.is_remote is True
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.published_at == datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    # Source tags are normalized into deterministic sorted order.
    assert posting.source_tags == ("Engineering", "Product")


def test_ashby_structured_salary_component_normalized() -> None:
    payload = _ashby_payload()
    payload["compensation"] = {
        "summaryComponents": [
            {
                "compensationType": "EquityPercentage",
                "interval": "NONE",
                "currencyCode": None,
                "minValue": None,
                "maxValue": None,
            },
            {
                "compensationType": "Salary",
                "interval": "1 YEAR",
                "currencyCode": "USD",
                "minValue": 211400,
                "maxValue": 290600,
            },
        ],
    }
    posting = normalize_ashby_job(_raw(ASHBY_SOURCE_PROVIDER, payload, "xyz-9"))

    from decimal import Decimal

    assert posting.salary_min == Decimal("211400")
    assert posting.salary_max == Decimal("290600")
    assert posting.salary_currency == "USD"
    from job_market_analyzer.models import SalaryPeriod

    assert posting.salary_period is SalaryPeriod.YEARLY


def test_ashby_equity_only_yields_no_salary() -> None:
    payload = _ashby_payload()
    payload["compensation"] = {
        "summaryComponents": [
            {
                "compensationType": "EquityPercentage",
                "interval": "NONE",
                "currencyCode": None,
                "minValue": None,
                "maxValue": None,
            },
        ],
    }
    posting = normalize_ashby_job(_raw(ASHBY_SOURCE_PROVIDER, payload, "xyz-9"))

    assert posting.salary_min is None
    assert posting.salary_max is None
    assert posting.salary_currency is None
    assert posting.salary_period is None


def test_ashby_malformed_compensation_is_tolerated() -> None:
    payload = _ashby_payload()
    payload["compensation"] = {"summaryComponents": ["garbage", 42]}
    posting = normalize_ashby_job(_raw(ASHBY_SOURCE_PROVIDER, payload, "xyz-9"))
    assert posting.salary_min is None


def test_hybrid_workplace_is_not_remote() -> None:
    payload = _lever_payload()
    payload["workplaceType"] = "hybrid"
    posting = normalize_lever_job(_raw(LEVER_SOURCE_PROVIDER, payload, "abc-123"))
    assert posting.is_remote is False


@pytest.mark.parametrize("field", ["workplaceType"])
def test_unsupported_lever_workplace_rejected(field: str) -> None:
    payload = _lever_payload()
    payload[field] = "unknown-value"
    with pytest.raises(LeverNormalizationError):
        normalize_lever_job(_raw(LEVER_SOURCE_PROVIDER, payload, "abc-123"))


def test_ashby_non_bool_remote_rejected() -> None:
    payload = _ashby_payload()
    payload["isRemote"] = "yes"
    with pytest.raises(AshbyNormalizationError):
        normalize_ashby_job(_raw(ASHBY_SOURCE_PROVIDER, payload, "xyz-9"))


def test_ashby_naive_datetime_rejected() -> None:
    payload = _ashby_payload()
    payload["publishedAt"] = "2026-08-01T10:00:00"
    with pytest.raises(AshbyNormalizationError, match="timezone"):
        normalize_ashby_job(_raw(ASHBY_SOURCE_PROVIDER, payload, "xyz-9"))


@pytest.mark.parametrize("provider", [LEVER_SOURCE_PROVIDER, ASHBY_SOURCE_PROVIDER])
def test_identity_mismatch_rejected(provider: str) -> None:
    payload = _lever_payload() if provider == LEVER_SOURCE_PROVIDER else _ashby_payload()
    normalizer = normalize_lever_job if provider == LEVER_SOURCE_PROVIDER else None
    if provider == LEVER_SOURCE_PROVIDER:
        with pytest.raises(LeverNormalizationError, match="identity"):
            normalizer(_raw(provider, payload, "other-id"))
    else:
        with pytest.raises(AshbyNormalizationError, match="identity"):
            normalize_ashby_job(_raw(provider, payload, "other-id"))
