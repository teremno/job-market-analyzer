from datetime import UTC, datetime

import pytest

from job_market_analyzer.collectors.greenhouse import GREENHOUSE_SOURCE_PROVIDER
from job_market_analyzer.models import RawJob
from job_market_analyzer.normalization.greenhouse import (
    GreenhouseNormalizationError,
    normalize_greenhouse_job,
)

FETCHED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _raw_job(
    payload: dict[str, object],
    *,
    source_scope: str = "gemini",
    external_id: str = "8065112",
) -> RawJob:
    return RawJob(
        source_provider=GREENHOUSE_SOURCE_PROVIDER,
        source_scope=source_scope,
        external_id=external_id,
        source_url="https://boards.greenhouse.io/gemini/jobs/8065112",
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def _payload() -> dict[str, object]:
    return {
        "id": "8065112",
        "title": "Analyst, Compliance (Investigations)",
        "company_name": "Gemini",
        "absolute_url": "https://boards.greenhouse.io/gemini/jobs/8065112",
        "content": "<h1>Role</h1><p>Investigate crypto cases.</p>",
        "location": {"name": "New York; Remote (USA)"},
        "first_published": "2026-07-15T15:54:49-04:00",
        "updated_at": "2026-07-30T12:49:21-04:00",
        "departments": [{"id": 1, "name": "Compliance"}],
        "offices": [{"id": 2, "name": "Gemini North America"}, {"not_name": True}],
    }


def test_normalizes_full_payload_with_structured_labels() -> None:
    posting = normalize_greenhouse_job(_raw_job(_payload()))

    assert posting.source_provider == "greenhouse"
    assert posting.source_scope == "gemini"
    assert posting.external_id == "8065112"
    assert posting.title == "Analyst, Compliance (Investigations)"
    assert posting.company_name == "Gemini"
    assert posting.description_text == "Role\nInvestigate crypto cases."
    assert posting.location_text == "New York; Remote (USA)"
    assert posting.application_url is not None
    assert str(posting.source_url).startswith("https://boards.greenhouse.io/")
    # Structured department/office names become source tags; malformed entries
    # are ignored without failing the vacancy.
    assert posting.source_tags == ("Compliance", "Gemini North America")
    # No salary or remote data is invented.
    assert posting.salary_text is None
    assert posting.salary_min is None
    assert posting.is_remote is None
    assert posting.remote_scope is None
    assert posting.employment_type is None
    assert posting.published_at == datetime(2026, 7, 15, 19, 54, 49, tzinfo=UTC)
    assert posting.source_updated_at == datetime(
        2026, 7, 30, 16, 49, 21, tzinfo=UTC
    )


def test_optional_fields_can_be_absent() -> None:
    payload = {
        "id": "42",
        "title": "Backend Engineer",
    }
    posting = normalize_greenhouse_job(_raw_job(payload, external_id="42"))

    assert posting.company_name is None
    assert posting.description_text is None
    assert posting.location_text is None
    assert posting.published_at is None
    assert posting.source_updated_at is None
    assert posting.source_tags == ()
    assert posting.source_url is None


def test_mismatched_identity_rejected() -> None:
    with pytest.raises(GreenhouseNormalizationError, match="identity"):
        normalize_greenhouse_job(_raw_job(_payload(), external_id="999"))


def test_wrong_provider_rejected() -> None:
    raw = RawJob(
        source_provider="himalayas",
        source_scope="global",
        external_id="x",
        source_url=None,
        fetched_at=FETCHED_AT,
        payload=_payload(),
    )
    with pytest.raises(GreenhouseNormalizationError):
        normalize_greenhouse_job(raw)


@pytest.mark.parametrize("field", ["first_published", "updated_at"])
def test_malformed_datetime_is_item_failure(field: str) -> None:
    payload = _payload()
    payload[field] = "not-a-datetime"
    with pytest.raises(GreenhouseNormalizationError, match=field):
        normalize_greenhouse_job(_raw_job(payload))


def test_naive_datetime_rejected() -> None:
    payload = _payload()
    payload["first_published"] = "2026-07-15T15:54:49"
    with pytest.raises(GreenhouseNormalizationError, match="timezone"):
        normalize_greenhouse_job(_raw_job(payload))


def test_missing_title_rejected() -> None:
    payload = _payload()
    del payload["title"]
    with pytest.raises(GreenhouseNormalizationError, match="title"):
        normalize_greenhouse_job(_raw_job(payload))


def test_integer_id_accepted_and_matched() -> None:
    payload = _payload()
    payload["id"] = 8065112
    raw = _raw_job(payload)
    posting = normalize_greenhouse_job(raw)
    assert posting.external_id == "8065112"


def test_invalid_url_rejected() -> None:
    payload = _payload()
    payload["absolute_url"] = "not-a-url"
    with pytest.raises(GreenhouseNormalizationError, match="URL"):
        normalize_greenhouse_job(_raw_job(payload))
