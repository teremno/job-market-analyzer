from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from job_market_analyzer.intelligence import calculate_skill_input_hash
from job_market_analyzer.models import JobPosting, RemoteScope, SalaryPeriod


def skill_hash(posting: JobPosting) -> str:
    return calculate_skill_input_hash(
        posting.title,
        posting.description_text,
        posting.source_tags,
    )


def make_posting(**overrides: object) -> JobPosting:
    values: dict[str, object] = {
        "id": uuid4(),
        "canonical_job_id": uuid4(),
        "source_provider": "remote_ok",
        "source_scope": "global",
        "external_id": "12345",
        "source_url": "https://remoteok.com/remote-jobs/12345",
        "title": "Python Developer",
        "company_name": "Example Company",
        "description_text": "Build Python services with Docker.",
        "source_tags": ("Docker", "Python"),
        "location_text": "Europe",
        "is_remote": True,
        "remote_scope": RemoteScope.REGION,
        "salary_min": Decimal(80000),
        "salary_max": Decimal(100000),
        "salary_currency": "USD",
        "salary_period": SalaryPeriod.YEARLY,
        "first_seen_at": datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        "last_seen_at": datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        "content_hash": "a" * 64,
    }
    values.update(overrides)
    return JobPosting(**values)


def test_identical_skill_analyzer_inputs_have_same_hash() -> None:
    posting = make_posting()

    assert skill_hash(posting) == skill_hash(posting.model_copy())


def test_semantically_normalized_source_tags_have_same_hash() -> None:
    first = calculate_skill_input_hash(
        "Python Developer",
        "Build services.",
        (" Python ", "Docker", "Python"),
    )
    second = calculate_skill_input_hash(
        "Python Developer",
        "Build services.",
        ("Docker", "Python"),
    )

    assert first == second


@pytest.mark.parametrize("empty_description", ["", "   ", "\t\n"])
def test_empty_descriptions_match_none_hash(empty_description: str) -> None:
    without_description = calculate_skill_input_hash(
        "Python Developer",
        None,
        ("Python",),
    )
    with_empty_description = calculate_skill_input_hash(
        "Python Developer",
        empty_description,
        ("Python",),
    )

    assert with_empty_description == without_description


@pytest.mark.parametrize(
    "change",
    [
        {"title": "Go Developer"},
        {"description_text": "Build Go services."},
        {"source_tags": ("Go",)},
    ],
)
def test_changed_skill_analyzer_input_changes_hash(change: dict[str, object]) -> None:
    posting = make_posting()

    assert skill_hash(posting) != skill_hash(posting.model_copy(update=change))


def test_non_skill_posting_fields_do_not_change_hash() -> None:
    posting = make_posting()
    non_skill_change = posting.model_copy(
        update={
            "company_name": "Renamed Company",
            "location_text": "Worldwide",
            "salary_min": Decimal(90000),
            "salary_max": Decimal(120000),
            "last_seen_at": posting.last_seen_at + timedelta(days=1),
            "content_hash": "b" * 64,
        }
    )

    assert skill_hash(posting) == skill_hash(non_skill_change)
