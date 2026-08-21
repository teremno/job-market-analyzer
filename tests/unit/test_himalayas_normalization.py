from datetime import UTC, datetime
from decimal import Decimal

import pytest

from job_market_analyzer.models import EmploymentType, RawJob, RemoteScope, SalaryPeriod
from job_market_analyzer.normalization.himalayas import (
    HimalayasNormalizationError,
    normalize_himalayas_job,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
GUID = "https://himalayas.app/companies/example/jobs/backend-engineer"


def raw(payload: dict[str, object]) -> RawJob:
    return RawJob(
        source_provider="himalayas",
        source_scope="global",
        external_id=GUID,
        source_url=GUID,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def test_normalizer_maps_identity_html_tags_remote_constraints_and_salary() -> None:
    posting = normalize_himalayas_job(
        raw(
            {
                "guid": GUID,
                "title": "Backend Engineer",
                "companyName": "Example",
                "description": "<p>Build APIs.</p>",
                "applicationLink": "https://example.com/apply",
                "categories": ["Engineering", "Python"],
                "parentCategories": ["Technology"],
                "locationRestrictions": ["Canada"],
                "timezoneRestrictions": [-8, -5],
                "employmentType": "Full Time",
                "minSalary": 100000,
                "maxSalary": 120000.5,
                "currency": "CAD",
                "salaryPeriod": "annual",
                "pubDate": 1787311412,
            }
        )
    )

    assert posting.external_id == GUID
    assert str(posting.application_url) == "https://example.com/apply"
    assert posting.description_text == "Build APIs."
    assert posting.source_tags == ("Engineering", "Python", "Technology")
    assert posting.location_text == "Canada"
    assert posting.remote_scope is RemoteScope.TIMEZONE
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.salary_min == Decimal("100000")
    assert posting.salary_max == Decimal("120000.5")
    assert posting.salary_currency == "CAD"
    assert posting.salary_period is SalaryPeriod.YEARLY
    assert posting.published_at == datetime.fromtimestamp(1787311412, tz=UTC)


def test_normalizer_preserves_missing_optional_fields() -> None:
    posting = normalize_himalayas_job(raw({"guid": GUID, "title": "General Job"}))

    assert posting.company_name is None
    assert posting.description_text is None
    assert posting.application_url is None
    assert posting.location_text is None
    assert posting.source_tags == ()
    assert posting.remote_scope is RemoteScope.UNSPECIFIED
    assert posting.salary_min is None
    assert posting.salary_currency is None
    assert posting.published_at is None


@pytest.mark.parametrize(
    "changes",
    [
        {"guid": "https://himalayas.app/jobs/different"},
        {"locationRestrictions": "Canada"},
        {"timezoneRestrictions": ["UTC-5"]},
        {"minSalary": "not-a-number"},
        {"applicationLink": "not-a-url"},
    ],
)
def test_normalizer_rejects_malformed_identity_and_optional_fields(
    changes: dict[str, object],
) -> None:
    payload: dict[str, object] = {"guid": GUID, "title": "Job"}
    payload.update(changes)
    with pytest.raises(HimalayasNormalizationError):
        normalize_himalayas_job(raw(payload))
