from datetime import UTC, datetime
from decimal import Decimal

import pytest

from job_market_analyzer.models import EmploymentType, RawJob, RemoteScope, SalaryPeriod
from job_market_analyzer.normalization.jobicy import (
    JobicyNormalizationError,
    normalize_jobicy_job,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
URL = "https://jobicy.com/jobs/101-backend-engineer"


def raw(payload: dict[str, object]) -> RawJob:
    return RawJob(
        source_provider="jobicy",
        source_scope="global",
        external_id="101",
        source_url=URL,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def test_normalizer_maps_native_fields_and_explicit_salary() -> None:
    posting = normalize_jobicy_job(
        raw(
            {
                "id": 101,
                "url": URL,
                "jobTitle": "Backend &amp; API Engineer",
                "companyName": "Example &amp; Co",
                "jobDescription": "<p>Build services.</p>",
                "jobIndustry": ["DevOps &amp; Infrastructure", "Engineering"],
                "jobType": ["Full-Time"],
                "jobGeo": "Anywhere",
                "salaryMin": 90000,
                "salaryMax": 110000,
                "salaryCurrency": "usd",
                "salaryPeriod": "yearly",
                "pubDate": "2026-08-21T09:46:14+00:00",
            }
        )
    )

    assert posting.title == "Backend & API Engineer"
    assert posting.company_name == "Example & Co"
    assert posting.description_text == "Build services."
    assert posting.source_tags == ("DevOps & Infrastructure", "Engineering")
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.remote_scope is RemoteScope.WORLDWIDE
    assert posting.salary_min == Decimal("90000")
    assert posting.salary_max == Decimal("110000")
    assert posting.salary_currency == "USD"
    assert posting.salary_period is SalaryPeriod.YEARLY
    assert posting.published_at == datetime(2026, 8, 21, 9, 46, 14, tzinfo=UTC)


def test_normalizer_keeps_missing_description_salary_and_location_empty() -> None:
    posting = normalize_jobicy_job(
        raw({"id": "101", "url": URL, "jobTitle": "QA Engineer"})
    )

    assert posting.description_text is None
    assert posting.location_text is None
    assert posting.remote_scope is RemoteScope.UNSPECIFIED
    assert posting.salary_min is None
    assert posting.salary_currency is None
    assert posting.employment_type is None


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "different"},
        {"jobIndustry": "Engineering"},
        {"jobType": [1]},
        {"salaryMin": "bad"},
        {"pubDate": "2026-08-21"},
    ],
)
def test_normalizer_rejects_malformed_identity_and_optional_fields(
    changes: dict[str, object],
) -> None:
    payload: dict[str, object] = {"id": 101, "url": URL, "jobTitle": "Job"}
    payload.update(changes)
    with pytest.raises(JobicyNormalizationError):
        normalize_jobicy_job(raw(payload))
