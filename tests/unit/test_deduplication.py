from datetime import UTC, datetime
from uuid import uuid4

from job_market_analyzer.models import CanonicalJob, JobPosting


def make_posting(
    *,
    source_provider: str,
    source_scope: str,
    external_id: str,
) -> JobPosting:
    now = datetime.now(UTC)

    return JobPosting(
        canonical_job_id=uuid4(),
        source_provider=source_provider,
        source_scope=source_scope,
        external_id=external_id,
        source_url="https://example.com/jobs/123",
        title="Python Developer",
        first_seen_at=now,
        last_seen_at=now,
        content_hash="abc123",
    )


def test_same_source_identity_is_equal_by_provider_scope_and_external_id() -> None:
    posting_a = make_posting(
        source_provider="greenhouse",
        source_scope="example-company",
        external_id="12345",
    )

    posting_b = make_posting(
        source_provider="greenhouse",
        source_scope="example-company",
        external_id="12345",
    )

    identity_a = (
        posting_a.source_provider,
        posting_a.source_scope,
        posting_a.external_id,
    )

    identity_b = (
        posting_b.source_provider,
        posting_b.source_scope,
        posting_b.external_id,
    )

    assert identity_a == identity_b


def test_same_external_id_in_different_scope_is_not_same_posting() -> None:
    posting_a = make_posting(
        source_provider="greenhouse",
        source_scope="company-a",
        external_id="12345",
    )

    posting_b = make_posting(
        source_provider="greenhouse",
        source_scope="company-b",
        external_id="12345",
    )

    identity_a = (
        posting_a.source_provider,
        posting_a.source_scope,
        posting_a.external_id,
    )

    identity_b = (
        posting_b.source_provider,
        posting_b.source_scope,
        posting_b.external_id,
    )

    assert identity_a != identity_b


def test_same_external_id_from_different_provider_is_not_same_posting() -> None:
    posting_a = make_posting(
        source_provider="greenhouse",
        source_scope="example-company",
        external_id="12345",
    )

    posting_b = make_posting(
        source_provider="remote_ok",
        source_scope="global",
        external_id="12345",
    )

    identity_a = (
        posting_a.source_provider,
        posting_a.source_scope,
        posting_a.external_id,
    )

    identity_b = (
        posting_b.source_provider,
        posting_b.source_scope,
        posting_b.external_id,
    )

    assert identity_a != identity_b


def test_cross_source_postings_can_share_one_canonical_job() -> None:
    now = datetime.now(UTC)

    canonical_job = CanonicalJob(
        created_at=now,
        updated_at=now,
    )

    posting_a = JobPosting(
        canonical_job_id=canonical_job.id,
        source_provider="greenhouse",
        source_scope="example-company",
        external_id="12345",
        source_url="https://example.com/greenhouse/12345",
        title="Python Developer",
        first_seen_at=now,
        last_seen_at=now,
        content_hash="hash-a",
    )

    posting_b = JobPosting(
        canonical_job_id=canonical_job.id,
        source_provider="remote_ok",
        source_scope="global",
        external_id="99999",
        source_url="https://example.com/remote-ok/99999",
        title="Python Developer",
        first_seen_at=now,
        last_seen_at=now,
        content_hash="hash-b",
    )

    assert posting_a.id != posting_b.id
    assert posting_a.canonical_job_id == posting_b.canonical_job_id
    assert posting_a.canonical_job_id == canonical_job.id


def test_new_models_receive_stable_independent_ids() -> None:
    now = datetime.now(UTC)

    canonical_job_a = CanonicalJob(
        created_at=now,
        updated_at=now,
    )

    canonical_job_b = CanonicalJob(
        created_at=now,
        updated_at=now,
    )

    assert canonical_job_a.id != canonical_job_b.id