import re
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from job_market_analyzer.models import (
    EmploymentType,
    JobPosting,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    SalaryPeriod,
)
from job_market_analyzer.storage.serialization import (
    calculate_content_hash,
    calculate_observation_hash,
    deserialize_source_tags,
    serialize_decimal,
    serialize_raw_payload,
    serialize_source_tags,
    serialize_utc_datetime,
)


def make_raw_job(
    *,
    fetched_at: datetime | None = None,
    payload: dict[str, object] | None = None,
) -> RawJob:
    return RawJob(
        source_provider="greenhouse",
        source_scope="example-company",
        external_id="12345",
        source_url="https://example.com/jobs/12345",
        fetched_at=fetched_at or datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
        payload=payload or {"title": "Python Developer"},
    )


def make_normalized_posting(
    **overrides: object,
) -> NormalizedJobPosting:
    values: dict[str, object] = {
        "source_provider": "greenhouse",
        "source_scope": "example-company",
        "external_id": "12345",
        "source_url": "https://example.com/jobs/12345",
        "application_url": "https://example.com/apply/12345",
        "title": "Python Developer",
        "company_name": "Example Company",
        "description_text": "Build reliable Python services.",
        "location_text": "Remote - Europe",
        "is_remote": True,
        "remote_scope": RemoteScope.REGION,
        "employment_type": EmploymentType.FULL_TIME,
        "salary_text": "EUR 40000 - 50000",
        "salary_min": Decimal("40000.00"),
        "salary_max": Decimal("50000.00"),
        "salary_currency": "EUR",
        "salary_period": SalaryPeriod.YEARLY,
        "published_at": datetime(2026, 8, 17, 12, 0, tzinfo=timezone(timedelta(hours=2))),
        "source_updated_at": datetime(2026, 8, 17, 10, 30, tzinfo=UTC),
    }
    values.update(overrides)
    return NormalizedJobPosting(**values)


def test_serialize_utc_datetime_uses_exact_utc_format() -> None:
    value = datetime(2026, 8, 17, 10, 11, 12, 123456, tzinfo=UTC)

    assert serialize_utc_datetime(value) == "2026-08-17T10:11:12.123456Z"


def test_serialize_utc_datetime_converts_non_utc_offset() -> None:
    value = datetime(
        2026,
        8,
        17,
        12,
        11,
        12,
        123456,
        tzinfo=timezone(timedelta(hours=2)),
    )

    assert serialize_utc_datetime(value) == "2026-08-17T10:11:12.123456Z"


def test_serialize_utc_datetime_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        serialize_utc_datetime(
            datetime(2026, 8, 17, 10, 11, 12)  # noqa: DTZ001
        )


def test_serialize_utc_datetime_always_includes_six_microsecond_digits() -> None:
    value = datetime(2026, 8, 17, 10, 11, 12, tzinfo=UTC)

    serialized = serialize_utc_datetime(value)

    assert serialized == "2026-08-17T10:11:12.000000Z"
    assert len(serialized) == 27


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("12345678901234567890.1200"), "12345678901234567890.12"),
        (Decimal("1E-8"), "0.00000001"),
        (Decimal("-0.000"), "0"),
    ],
)
def test_serialize_decimal_is_exact(value: Decimal, expected: str) -> None:
    assert serialize_decimal(value) == expected


def test_raw_payload_json_is_deterministic_for_key_order() -> None:
    first = {"b": 2, "nested": {"z": 3, "a": 1}, "a": "value"}
    second = {"a": "value", "nested": {"a": 1, "z": 3}, "b": 2}

    assert serialize_raw_payload(first) == serialize_raw_payload(second)
    assert serialize_raw_payload(first) == (
        '{"a":"value","b":2,"nested":{"a":1,"z":3}}'
    )


def test_raw_payload_json_rejects_nan() -> None:
    with pytest.raises(ValueError):
        serialize_raw_payload({"score": float("nan")})


def test_raw_payload_json_rejects_arbitrary_objects() -> None:
    with pytest.raises(TypeError):
        serialize_raw_payload({"value": object()})


@pytest.mark.parametrize(
    ("source_tags", "serialized"),
    [
        ((), "[]"),
        (("Docker", "Python"), '["Docker","Python"]'),
        (("Солідність", "数据"), '["Солідність","数据"]'),
    ],
)
def test_source_tags_round_trip_as_canonical_json(
    source_tags: tuple[str, ...],
    serialized: str,
) -> None:
    assert serialize_source_tags(source_tags) == serialized
    assert deserialize_source_tags(serialized) == source_tags


@pytest.mark.parametrize(
    ("serialized", "expected_error"),
    [
        ("{}", "must contain a JSON array"),
        ('["Python",1]', "array items must be strings"),
    ],
)
def test_deserialize_source_tags_rejects_corrupted_persisted_state(
    serialized: str,
    expected_error: str,
) -> None:
    with pytest.raises(TypeError, match=expected_error):
        deserialize_source_tags(serialized)


def test_observation_hash_is_lowercase_sha256() -> None:
    observation_hash = calculate_observation_hash(make_raw_job())

    assert re.fullmatch(r"[0-9a-f]{64}", observation_hash)


def test_observation_hash_excludes_raw_job_id() -> None:
    first = make_raw_job()
    second = first.model_copy(update={"id": uuid4()})

    assert first.id != second.id
    assert calculate_observation_hash(first) == calculate_observation_hash(second)


def test_observation_hash_excludes_fetched_at() -> None:
    first = make_raw_job()
    second = first.model_copy(
        update={"fetched_at": datetime(2026, 8, 18, 10, 0, tzinfo=UTC)}
    )

    assert calculate_observation_hash(first) == calculate_observation_hash(second)


def test_observation_hash_changes_with_payload() -> None:
    first = make_raw_job(payload={"title": "Python Developer"})
    second = make_raw_job(payload={"title": "Senior Python Developer"})

    assert calculate_observation_hash(first) != calculate_observation_hash(second)


def test_content_hash_is_deterministic() -> None:
    posting = make_normalized_posting()

    assert calculate_content_hash(posting) == calculate_content_hash(posting)


def test_content_hash_excludes_persistence_lifecycle_fields() -> None:
    normalized = make_normalized_posting()
    normalized_values = normalized.model_dump()

    first = JobPosting(
        **normalized_values,
        id=uuid4(),
        canonical_job_id=uuid4(),
        first_seen_at=datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
        last_seen_at=datetime(2026, 8, 17, 11, 0, tzinfo=UTC),
        content_hash="a" * 64,
    )
    second = JobPosting(
        **normalized_values,
        id=uuid4(),
        canonical_job_id=uuid4(),
        first_seen_at=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        last_seen_at=datetime(2026, 8, 19, 11, 0, tzinfo=UTC),
        content_hash="b" * 64,
    )

    assert calculate_content_hash(first) == calculate_content_hash(second)


def test_content_hash_changes_with_persisted_normalized_field() -> None:
    first = make_normalized_posting(title="Python Developer")
    second = make_normalized_posting(title="Senior Python Developer")

    assert calculate_content_hash(first) != calculate_content_hash(second)


def test_content_hash_is_stable_for_semantically_equal_source_tags() -> None:
    first = make_normalized_posting(source_tags=[" Python ", "Docker", "Python"])
    second = make_normalized_posting(source_tags=["Docker", "Python"])

    assert first.source_tags == second.source_tags == ("Docker", "Python")
    assert calculate_content_hash(first) == calculate_content_hash(second)


def test_content_hash_changes_with_normalized_source_tags() -> None:
    without_docker = make_normalized_posting(source_tags=["Python"])
    with_docker = make_normalized_posting(source_tags=["Python", "Docker"])

    assert calculate_content_hash(without_docker) != calculate_content_hash(
        with_docker
    )


def test_content_hash_normalizes_supported_persistence_types() -> None:
    first = make_normalized_posting(
        salary_min=Decimal("40000.00"),
        published_at=datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone(timedelta(hours=2)),
        ),
    )
    second = make_normalized_posting(
        salary_min=Decimal("4E+4"),
        published_at=datetime(2026, 8, 17, 10, 0, tzinfo=UTC),
    )

    assert first.remote_scope is RemoteScope.REGION
    assert first.salary_period is SalaryPeriod.YEARLY
    assert str(first.source_url) == str(second.source_url)
    assert calculate_content_hash(first) == calculate_content_hash(second)
