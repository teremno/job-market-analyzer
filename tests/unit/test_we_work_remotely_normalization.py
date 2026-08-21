from datetime import UTC, datetime

import pytest

from job_market_analyzer.models import EmploymentType, RawJob, RemoteScope
from job_market_analyzer.normalization.we_work_remotely import (
    WeWorkRemotelyNormalizationError,
    normalize_we_work_remotely_job,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
URL = "https://weworkremotely.com/remote-jobs/example-backend-engineer"


def raw(payload: dict[str, object]) -> RawJob:
    return RawJob(
        source_provider="we_work_remotely",
        source_scope="global",
        external_id=URL,
        source_url=URL,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def test_normalizer_maps_rss_title_location_tags_and_timestamp() -> None:
    posting = normalize_we_work_remotely_job(
        raw(
            {
                "guid": URL,
                "link": URL,
                "title": "Example &amp; Co: Backend Engineer",
                "description": "<p>Build APIs.</p>",
                "region": "Anywhere in the World",
                "state": "Texas",
                "category": "Back-End Programming",
                "skills": "Python and APIs",
                "type": "Full-Time",
                "pubDate": "Fri, 21 Aug 2026 10:40:25 +0000",
            }
        )
    )

    assert posting.title == "Backend Engineer"
    assert posting.company_name == "Example & Co"
    assert posting.description_text == "Build APIs."
    assert posting.location_text == "Anywhere in the World, Texas"
    assert posting.remote_scope is RemoteScope.WORLDWIDE
    assert posting.source_tags == ("Back-End Programming", "Python and APIs")
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.published_at == datetime(2026, 8, 21, 10, 40, 25, tzinfo=UTC)


def test_normalizer_handles_title_without_company_and_missing_optional_fields() -> None:
    posting = normalize_we_work_remotely_job(
        raw({"guid": URL, "link": URL, "title": "General Application"})
    )

    assert posting.title == "General Application"
    assert posting.company_name is None
    assert posting.description_text is None
    assert posting.location_text is None
    assert posting.remote_scope is RemoteScope.UNSPECIFIED
    assert posting.salary_text is None
    assert posting.application_url is None


@pytest.mark.parametrize(
    "changes",
    [
        {"guid": "https://weworkremotely.com/remote-jobs/different"},
        {"region": 1},
        {"pubDate": "not-a-date"},
    ],
)
def test_normalizer_rejects_malformed_identity_and_optional_fields(
    changes: dict[str, object],
) -> None:
    payload: dict[str, object] = {"guid": URL, "link": URL, "title": "Job"}
    payload.update(changes)
    with pytest.raises(WeWorkRemotelyNormalizationError):
        normalize_we_work_remotely_job(raw(payload))
