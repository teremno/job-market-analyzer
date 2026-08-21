from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from job_market_analyzer.intelligence import calculate_role_input_hash
from job_market_analyzer.models import JobPosting, NormalizedJobPosting


def test_same_role_inputs_have_same_hash() -> None:
    assert calculate_role_input_hash(
        "Backend Engineer", "Build reliable APIs."
    ) == calculate_role_input_hash("Backend Engineer", "Build reliable APIs.")


def test_absent_descriptions_have_same_hash() -> None:
    hashes = {
        calculate_role_input_hash("Backend Engineer", description)
        for description in (None, "", " \t\n ")
    }
    assert len(hashes) == 1


def test_changed_title_changes_hash() -> None:
    assert calculate_role_input_hash(
        "Backend Engineer", "Build APIs."
    ) != calculate_role_input_hash("Product Manager", "Build APIs.")


def test_changed_description_changes_hash() -> None:
    assert calculate_role_input_hash(
        "Backend Engineer", "Build APIs."
    ) != calculate_role_input_hash("Backend Engineer", "Build protocols.")


def test_non_role_fields_are_not_role_hash_inputs() -> None:
    def posting(**changes: object) -> NormalizedJobPosting:
        values: dict[str, object] = {
            "source_provider": "test",
            "source_scope": "global",
            "external_id": "1",
            "title": "Backend Engineer",
            "description_text": "Build APIs.",
        }
        values.update(changes)
        return NormalizedJobPosting(**values)

    baseline_posting = posting()
    baseline = calculate_role_input_hash(
        baseline_posting.title, baseline_posting.description_text
    )
    variants = (
        posting(salary_min=Decimal(100000), salary_currency="USD"),
        posting(location_text="Europe"),
        posting(company_name="Renamed Company"),
        posting(source_tags=("Python",)),
        posting(source_url="https://example.test/source"),
        posting(application_url="https://example.test/apply"),
        posting(source_provider="other", source_scope="regional", external_id="2"),
        posting(source_updated_at=datetime(2026, 8, 21, tzinfo=UTC)),
    )
    assert all(
        calculate_role_input_hash(item.title, item.description_text) == baseline
        for item in variants
    )


def test_persistence_identity_and_lifecycle_fields_are_not_role_hash_inputs() -> None:
    now = datetime(2026, 8, 21, tzinfo=UTC)

    def posting(**changes: object) -> JobPosting:
        values: dict[str, object] = {
            "id": uuid4(),
            "canonical_job_id": uuid4(),
            "source_provider": "test",
            "source_scope": "global",
            "external_id": "1",
            "title": "Backend Engineer",
            "description_text": "Build APIs.",
            "first_seen_at": now,
            "last_seen_at": now,
            "content_hash": "a" * 64,
        }
        values.update(changes)
        return JobPosting(**values)

    baseline = posting()
    changed = posting(
        id=uuid4(),
        canonical_job_id=uuid4(),
        first_seen_at=now - timedelta(days=1),
        last_seen_at=now + timedelta(days=1),
        content_hash="b" * 64,
    )
    assert calculate_role_input_hash(
        baseline.title, baseline.description_text
    ) == calculate_role_input_hash(changed.title, changed.description_text)


def test_nonblank_title_and_description_whitespace_remains_part_of_input() -> None:
    assert calculate_role_input_hash(
        "Backend Engineer", "Build APIs."
    ) != calculate_role_input_hash(" Backend Engineer ", " Build APIs. ")


def test_unicode_role_hash_is_deterministic() -> None:
    assert calculate_role_input_hash(
        "Інженер Backend", "Розробка сервісів"
    ) == calculate_role_input_hash("Інженер Backend", "Розробка сервісів")


def test_structured_serialization_avoids_concatenation_ambiguity() -> None:
    assert calculate_role_input_hash("ab", "c") != calculate_role_input_hash("a", "bc")
