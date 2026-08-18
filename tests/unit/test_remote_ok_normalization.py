from datetime import UTC, datetime

import pytest

from job_market_analyzer.models import EmploymentType, RawJob, RemoteScope
from job_market_analyzer.normalization.remote_ok import (
    RemoteOKNormalizationError,
    normalize_remote_ok_job,
)

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def make_raw_job(payload: dict[str, object]) -> RawJob:
    return RawJob(
        source_provider="remote_ok",
        source_scope="global",
        external_id=str(payload.get("id", "101")),
        source_url="https://remoteok.com/remote-jobs/python-developer-101",
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def test_normalizer_maps_representative_remote_ok_payload() -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "position": "Python Developer",
            "company": "Example Company",
            "description": (
                "<p>Build reliable APIs.</p><ul><li>Python</li><li>HTTP</li></ul>"
            ),
            "location": "Worldwide",
            "tags": ["python", "full time"],
            "date": "2026-08-17T10:30:00+00:00",
            "apply_url": "https://example.com/apply/101",
            "salary_min": 100000,
            "salary_max": 140000,
        }
    )

    posting = normalize_remote_ok_job(raw_job)

    assert posting.external_id == "101"
    assert str(posting.source_url) == str(raw_job.source_url)
    assert str(posting.application_url) == "https://example.com/apply/101"
    assert posting.title == "Python Developer"
    assert posting.company_name == "Example Company"
    assert posting.description_text == "Build reliable APIs.\nPython\nHTTP"
    assert posting.source_tags == ("full time", "python")
    assert raw_job.payload["tags"] == ["python", "full time"]
    assert posting.location_text == "Worldwide"
    assert posting.is_remote is True
    assert posting.remote_scope is RemoteScope.WORLDWIDE
    assert posting.employment_type is EmploymentType.FULL_TIME
    assert posting.published_at == datetime(2026, 8, 17, 10, 30, tzinfo=UTC)
    assert posting.source_updated_at is None
    assert posting.salary_text is None
    assert posting.salary_min is None
    assert posting.salary_max is None
    assert posting.salary_currency is None
    assert posting.salary_period is None


def test_normalizer_keeps_missing_optional_fields_empty() -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "position": "QA Engineer",
            "apply_url": "https://remoteok.com/remote-jobs/python-developer-101",
        }
    )

    posting = normalize_remote_ok_job(raw_job)

    assert posting.title == "QA Engineer"
    assert posting.company_name is None
    assert posting.description_text is None
    assert posting.source_tags == ()
    assert posting.location_text is None
    assert posting.application_url is None
    assert posting.is_remote is True
    assert posting.remote_scope is RemoteScope.UNSPECIFIED
    assert posting.employment_type is None
    assert posting.published_at is None


def test_normalizer_accepts_explicit_null_optional_fields() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "QA Engineer",
                "company": None,
                "description": None,
                "location": None,
                "apply_url": None,
                "tags": None,
                "date": None,
                "epoch": None,
            }
        )
    )

    assert posting.company_name is None
    assert posting.description_text is None
    assert posting.source_tags == ()
    assert posting.location_text is None
    assert posting.application_url is None
    assert posting.employment_type is None
    assert posting.published_at is None


def test_normalizer_ignores_only_malformed_optional_tag_elements() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "tags": [" full-time ", 123, "Python", "Python"],
            }
        )
    )

    assert posting.source_tags == ("full-time", "Python")
    assert posting.employment_type is EmploymentType.FULL_TIME


def test_normalizer_excludes_script_content() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "description": "<p>Visible</p><script>hidden()</script><p>After</p>",
            }
        )
    )

    assert posting.description_text == "Visible\nAfter"


def test_normalizer_excludes_style_content() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "description": "<style>.hidden { display: none; }</style><p>Visible</p>",
            }
        )
    )

    assert posting.description_text == "Visible"


def test_normalizer_separates_adjacent_inline_nodes() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "description": "<span>Remote</span><span>job</span>",
            }
        )
    )

    assert posting.description_text == "Remote job"


def test_normalizer_decodes_html_entities_exactly_once() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "description": "<p>&amp;lt;literal&amp;gt;</p>",
            }
        )
    )

    assert posting.description_text == "&lt;literal&gt;"


def test_normalizer_handles_malformed_html() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "description": "<p>Remote <strong>job",
            }
        )
    )

    assert posting.description_text == "Remote job"


def test_normalizer_collapses_excessive_whitespace_predictably() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "description": (
                    "<div>  Remote \n\t job  </div><p>  Build   APIs  </p>"
                ),
            }
        )
    )

    assert posting.description_text == "Remote job\nBuild APIs"


def test_normalizer_preserves_distinct_case_sensitive_application_path() -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "position": "Developer",
            "apply_url": "https://remoteok.com/remote-jobs/Python-developer-101",
        }
    )

    posting = normalize_remote_ok_job(raw_job)

    assert str(posting.application_url) == (
        "https://remoteok.com/remote-jobs/Python-developer-101"
    )


def test_normalizer_does_not_classify_restricted_location_as_worldwide() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "location": "Europe only",
            }
        )
    )

    assert posting.remote_scope is RemoteScope.UNSPECIFIED


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("full-time", EmploymentType.FULL_TIME),
        ("contract", EmploymentType.CONTRACT),
        ("freelance", EmploymentType.FREELANCE),
        ("internship", EmploymentType.INTERNSHIP),
    ],
)
def test_normalizer_infers_exact_employment_type_tags(
    tag: str,
    expected: EmploymentType,
) -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Developer",
                "tags": [tag],
            }
        )
    )

    assert posting.employment_type is expected


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "101"},
        {"id": "101", "position": "   "},
        {"id": "different", "position": "Developer"},
    ],
)
def test_normalizer_rejects_malformed_required_fields(
    payload: dict[str, object],
) -> None:
    raw_job = make_raw_job(payload)
    if payload["id"] == "different":
        raw_job = raw_job.model_copy(update={"external_id": "101"})

    with pytest.raises(RemoteOKNormalizationError):
        normalize_remote_ok_job(raw_job)


def test_normalizer_uses_epoch_when_date_is_absent() -> None:
    raw_job = make_raw_job(
        {
            "id": "101",
            "position": "Data Analyst",
            "epoch": 1786960800,
        }
    )

    posting = normalize_remote_ok_job(raw_job)

    assert posting.published_at == datetime.fromtimestamp(1786960800, tz=UTC)


def test_normalizer_prefers_date_over_epoch() -> None:
    posting = normalize_remote_ok_job(
        make_raw_job(
            {
                "id": "101",
                "position": "Data Analyst",
                "date": "2026-08-17T10:30:00+00:00",
                "epoch": 0,
            }
        )
    )

    assert posting.published_at == datetime(2026, 8, 17, 10, 30, tzinfo=UTC)
