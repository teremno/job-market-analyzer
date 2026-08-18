from datetime import UTC, datetime

import pytest

from job_market_analyzer.models import RawJob, RemoteScope
from job_market_analyzer.normalization.web3_career import (
    Web3CareerNormalizationError,
    normalize_web3_career_job,
)

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
APPLY_URL = "https://web3.career/redirect/101?source=api"
SOURCE_URL = "https://web3.career/solidity-engineer-chain-labs/101"


def make_raw_job(payload: dict[str, object]) -> RawJob:
    complete_payload = {
        "apply_url": APPLY_URL,
        **payload,
    }
    return RawJob(
        source_provider="web3_career",
        source_scope="global",
        external_id=str(complete_payload.get("id", "101")),
        source_url=complete_payload.get("url"),
        fetched_at=FETCHED_AT,
        payload=complete_payload,
    )


def test_normalizer_maps_representative_web3_career_payload() -> None:
    raw_job = make_raw_job(
        {
            "id": 101,
            "title": "Solidity Engineer",
            "company": "Chain Labs",
            "location": "Europe only",
            "remote": True,
            "description": (
                "<p>Build secure contracts.</p><script>hidden()</script>"
                "<span>Remote</span><span>role</span>"
            ),
            "tags": ["solidity", "full-time"],
            "apply_url": APPLY_URL,
            "url": SOURCE_URL,
            "salary": "$100k-$140k",
            "salary_min_value": 100000,
            "salary_max_value": "140000",
            "salary_currency": "usd",
            "salary_unit": "year",
            "date": "2026-08-17T10:30:00Z",
        }
    )

    posting = normalize_web3_career_job(raw_job)

    assert posting.external_id == "101"
    assert str(posting.source_url) == SOURCE_URL
    assert str(posting.application_url) == APPLY_URL
    assert posting.title == "Solidity Engineer"
    assert posting.company_name == "Chain Labs"
    assert posting.description_text == "Build secure contracts.\nRemote role"
    assert posting.source_tags == ("full-time", "solidity")
    assert raw_job.payload["tags"] == ["solidity", "full-time"]
    assert posting.location_text == "Europe only"
    assert posting.is_remote is True
    assert posting.remote_scope is RemoteScope.UNSPECIFIED
    assert posting.employment_type is None
    assert posting.salary_text == "$100k-$140k"
    assert posting.salary_min is None
    assert posting.salary_max is None
    assert posting.salary_currency is None
    assert posting.salary_period is None
    assert posting.published_at == datetime(2026, 8, 17, 10, 30, tzinfo=UTC)
    assert posting.source_updated_at is None


def test_normalizer_keeps_explicit_null_optional_fields_empty() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Protocol Engineer",
                "company": None,
                "location": None,
                "city": None,
                "country": None,
                "description": None,
                "tags": None,
                "url": None,
                "remote": None,
                "is_remote": None,
                "apply_url": APPLY_URL,
                "salary": None,
                "salary_min_value": None,
                "salary_max_value": None,
                "date": None,
                "postedAt": None,
                "date_epoch": None,
            }
        )
    )

    assert posting.company_name is None
    assert posting.source_url is None
    assert posting.description_text is None
    assert posting.source_tags == ()
    assert posting.location_text is None
    assert posting.is_remote is None
    assert posting.remote_scope is None
    assert posting.employment_type is None
    assert posting.salary_text is None
    assert posting.salary_min is None
    assert posting.salary_max is None
    assert posting.salary_currency is None
    assert posting.salary_period is None
    assert posting.published_at is None


def test_normalizer_ignores_only_malformed_optional_tag_elements() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Protocol Engineer",
                "tags": [" Solidity ", None, "智能 合约", "Solidity"],
            }
        )
    )

    assert posting.source_tags == ("Solidity", "智能 合约")
    assert posting.employment_type is None


def test_normalizer_preserves_application_url_when_source_url_is_missing() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Protocol Engineer",
                "apply_url": APPLY_URL,
            }
        )
    )

    assert posting.source_url is None
    assert str(posting.application_url) == APPLY_URL


def test_normalizer_builds_country_location_and_scope() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Security Engineer",
                "city": "Berlin",
                "country": "Germany",
                "is_remote": True,
                "apply_url": APPLY_URL,
            }
        )
    )

    assert posting.location_text == "Berlin, Germany"
    assert posting.remote_scope is RemoteScope.COUNTRY


def test_normalizer_recognizes_exact_worldwide_location() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Developer",
                "location": "Worldwide",
                "remote": True,
                "apply_url": APPLY_URL,
            }
        )
    )

    assert posting.remote_scope is RemoteScope.WORLDWIDE


def test_normalizer_country_restriction_takes_priority_over_worldwide_text() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Developer",
                "location": "Worldwide",
                "country": "Germany",
                "remote": True,
            }
        )
    )

    assert posting.remote_scope is RemoteScope.COUNTRY


def test_normalizer_does_not_infer_remote_scope_when_not_remote() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Developer",
                "location": "Worldwide",
                "remote": False,
                "apply_url": APPLY_URL,
            }
        )
    )

    assert posting.is_remote is False
    assert posting.remote_scope is None


def test_normalizer_uses_epoch_when_dates_are_absent() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Data Analyst",
                "apply_url": APPLY_URL,
                "date_epoch": 1786960800,
            }
        )
    )

    assert posting.published_at == datetime.fromtimestamp(1786960800, tz=UTC)


def test_normalizer_accepts_official_posted_at_field() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Data Analyst",
                "apply_url": APPLY_URL,
                "postedAt": "2026-08-17",
            }
        )
    )

    assert posting.published_at == datetime(2026, 8, 17, tzinfo=UTC)


@pytest.mark.parametrize(
    "unconfirmed_salary_fields",
    [
        {"salary_min_value": 120000},
        {"salary_max_value": 160000},
        {"salary_min_value": 0, "salary_max_value": 0},
        {"salary_min_value": "120000", "salary_max_value": "invalid"},
        {"salary_currency": "USD", "salary_unit": "year"},
        {
            "estimated_min_salary": 120000,
            "estimated_max_salary": 160000,
            "estimated_avg_salary": 140000,
        },
    ],
)
def test_normalizer_keeps_unconfirmed_salary_fields_raw_only(
    unconfirmed_salary_fields: dict[str, object],
) -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "title": "Developer",
            **unconfirmed_salary_fields,
        }
    )

    posting = normalize_web3_career_job(raw_job)

    assert posting.salary_text is None
    assert posting.salary_min is None
    assert posting.salary_max is None
    assert posting.salary_currency is None
    assert posting.salary_period is None
    for field_name, value in unconfirmed_salary_fields.items():
        assert raw_job.payload[field_name] == value


@pytest.mark.parametrize(
    ("date_fields", "expected"),
    [
        (
            {
                "date": "2026-08-17T10:30:00Z",
                "postedAt": "2026-08-16T10:30:00Z",
                "date_epoch": 0,
            },
            datetime(2026, 8, 17, 10, 30, tzinfo=UTC),
        ),
        (
            {
                "date": "not-a-date",
                "postedAt": "2026-08-16",
                "date_epoch": 0,
            },
            datetime(2026, 8, 16, tzinfo=UTC),
        ),
        (
            {
                "postedAt": "unknown format",
                "date_epoch": 1786960800,
            },
            datetime.fromtimestamp(1786960800, tz=UTC),
        ),
        (
            {
                "date": "invalid",
                "postedAt": {"unexpected": "shape"},
                "date_epoch": "invalid",
            },
            None,
        ),
    ],
)
def test_normalizer_uses_first_valid_publication_date(
    date_fields: dict[str, object],
    expected: datetime | None,
) -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Developer",
                **date_fields,
            }
        )
    )

    assert posting.published_at == expected


def test_normalizer_does_not_infer_employment_type_from_tags() -> None:
    posting = normalize_web3_career_job(
        make_raw_job(
            {
                "id": "101",
                "title": "Developer",
                "apply_url": APPLY_URL,
                "tags": ["full-time", "contract"],
            }
        )
    )

    assert posting.employment_type is None


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "101", "apply_url": APPLY_URL},
        {"id": "101", "title": "   ", "apply_url": APPLY_URL},
        {"id": "different", "title": "Developer", "apply_url": APPLY_URL},
    ],
)
def test_normalizer_rejects_malformed_required_identity(
    payload: dict[str, object],
) -> None:
    raw_job = make_raw_job(payload)
    if payload["id"] == "different":
        raw_job = raw_job.model_copy(update={"external_id": "101"})

    with pytest.raises(Web3CareerNormalizationError):
        normalize_web3_career_job(raw_job)


def test_normalizer_rejects_conflicting_remote_fields() -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "title": "Developer",
            "apply_url": APPLY_URL,
            "remote": True,
            "is_remote": False,
        }
    )

    with pytest.raises(Web3CareerNormalizationError, match="conflicting"):
        normalize_web3_career_job(raw_job)


def test_normalizer_rejects_source_url_provenance_mismatch() -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "title": "Developer",
            "apply_url": APPLY_URL,
        }
    ).model_copy(update={"source_url": "https://web3.career/jobs/other"})

    with pytest.raises(Web3CareerNormalizationError, match="does not match"):
        normalize_web3_career_job(raw_job)
