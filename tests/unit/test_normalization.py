from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from job_market_analyzer.models import (
    CanonicalJob,
    EmploymentType,
    JobPosting,
    RemoteScope,
    SalaryPeriod,
)

VALID_CONTENT_HASH = "a" * 64


def test_job_posting_accepts_valid_data() -> None:
    now = datetime.now(UTC)

    posting = JobPosting(
        canonical_job_id=uuid4(),
        source_provider="Remote_OK",
        source_scope="GLOBAL",
        external_id="12345",
        source_url="https://remoteok.com/remote-jobs/12345",
        application_url="https://example.com/apply",
        title="Python Automation Developer",
        company_name="Example Company",
        description_text="Build Python automation tools.",
        location_text="Remote - Europe",
        is_remote=True,
        remote_scope=RemoteScope.REGION,
        employment_type=EmploymentType.CONTRACT,
        salary_text="€40,000 - €50,000",
        salary_min=Decimal(40000),
        salary_max=Decimal(50000),
        salary_currency="eur",
        salary_period=SalaryPeriod.YEARLY,
        published_at=now,
        first_seen_at=now,
        last_seen_at=now,
        content_hash=VALID_CONTENT_HASH,
    )

    assert posting.source_provider == "remote_ok"
    assert posting.source_scope == "global"
    assert posting.external_id == "12345"

    assert posting.salary_currency == "EUR"
    assert posting.salary_min == Decimal(40000)

    assert posting.remote_scope is RemoteScope.REGION
    assert posting.employment_type is EmploymentType.CONTRACT


def test_job_posting_rejects_invalid_salary_range() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        JobPosting(
            canonical_job_id=uuid4(),
            source_provider="remote_ok",
            source_scope="global",
            external_id="12345",
            source_url="https://remoteok.com/remote-jobs/12345",
            title="Python Developer",
            salary_min=Decimal(60000),
            salary_max=Decimal(50000),
            first_seen_at=now,
            last_seen_at=now,
            content_hash=VALID_CONTENT_HASH,
        )


def test_job_posting_rejects_invalid_seen_range() -> None:
    first_seen = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    last_seen = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        JobPosting(
            canonical_job_id=uuid4(),
            source_provider="remote_ok",
            source_scope="global",
            external_id="12345",
            source_url="https://remoteok.com/remote-jobs/12345",
            title="Python Developer",
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            content_hash=VALID_CONTENT_HASH,
        )


def test_job_posting_rejects_invalid_content_hash_length() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        JobPosting(
            canonical_job_id=uuid4(),
            source_provider="remote_ok",
            source_scope="global",
            external_id="12345",
            source_url="https://remoteok.com/remote-jobs/12345",
            title="Python Developer",
            first_seen_at=now,
            last_seen_at=now,
            content_hash="abc123",
        )


def test_job_posting_rejects_non_hex_content_hash() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ValidationError):
        JobPosting(
            canonical_job_id=uuid4(),
            source_provider="remote_ok",
            source_scope="global",
            external_id="12345",
            source_url="https://remoteok.com/remote-jobs/12345",
            title="Python Developer",
            first_seen_at=now,
            last_seen_at=now,
            content_hash="z" * 64,
        )


def test_canonical_job_rejects_invalid_timestamp_range() -> None:
    created_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    updated_at = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        CanonicalJob(
            created_at=created_at,
            updated_at=updated_at,
        )