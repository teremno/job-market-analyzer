from datetime import UTC, datetime

import pytest

from job_market_analyzer.models import EmploymentType, RawJob, RemoteScope
from job_market_analyzer.normalization.remotive import (
    RemotiveNormalizationError,
    normalize_remotive_job,
)

FETCHED_AT = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
URL = "https://remotive.com/remote-jobs/software-dev/backend-engineer-101"


def raw(payload: dict[str, object]) -> RawJob:
    return RawJob(
        source_provider="remotive",
        source_scope="global",
        external_id="101",
        source_url=URL,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def test_normalizer_maps_attributed_url_tags_and_raw_salary_text() -> None:
    posting = normalize_remotive_job(
        raw(
            {
                "id": 101,
                "url": URL,
                "title": "Backend Engineer",
                "company_name": "Example",
                "description": "<p>Build APIs.</p>",
                "candidate_required_location": "Worldwide",
                "category": "Software Development",
                "tags": ["Python", "API"],
                "job_type": "full_time",
                "salary": "$100k - $120k",
                "publication_date": "2026-08-20T09:54:55",
            }
        )
    )

    assert posting.description_text == "Build APIs."
    assert posting.source_tags == ("API", "Python", "Software Development")
    assert posting.remote_scope is RemoteScope.WORLDWIDE
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.salary_text == "$100k - $120k"
    assert posting.salary_min is None
    assert posting.published_at == datetime(2026, 8, 20, 9, 54, 55, tzinfo=UTC)


def test_normalizer_keeps_missing_optional_fields_empty() -> None:
    posting = normalize_remotive_job(raw({"id": "101", "url": URL, "title": "Job"}))

    assert posting.company_name is None
    assert posting.description_text is None
    assert posting.location_text is None
    assert posting.salary_text is None
    assert posting.source_tags == ()
    assert posting.remote_scope is RemoteScope.UNSPECIFIED


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "different"},
        {"tags": "Python"},
        {"candidate_required_location": 1},
        {"publication_date": "not-a-date"},
    ],
)
def test_normalizer_rejects_malformed_identity_and_optional_fields(
    changes: dict[str, object],
) -> None:
    payload: dict[str, object] = {"id": 101, "url": URL, "title": "Job"}
    payload.update(changes)
    with pytest.raises(RemotiveNormalizationError):
        normalize_remotive_job(raw(payload))
