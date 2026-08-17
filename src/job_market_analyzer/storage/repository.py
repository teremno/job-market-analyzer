from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from job_market_analyzer.models import NormalizedJobPosting, RawJob


class SourceIdentityMismatchError(ValueError):
    """Raised when raw and normalized records identify different postings."""


@dataclass(frozen=True)
class PersistResult:
    """Result of persisting one collected job observation."""

    canonical_job_id: UUID
    job_posting_id: UUID
    raw_job_id: UUID | None

    canonical_created: bool
    posting_created: bool
    raw_observation_created: bool


class JobRepository(Protocol):
    """Storage contract used by application services."""

    def persist_observation(
        self,
        raw_job: RawJob,
        posting: NormalizedJobPosting,
    ) -> PersistResult:
        """
        Persist one collected source observation atomically.

        Implementations must:

        - verify that RawJob and NormalizedJobPosting have the same
          source identity:
          (source_provider, source_scope, external_id);

        - identify durable JobPosting records by:
          (source_provider, source_scope, external_id);

        - create job_posting_id for a new durable source posting;

        - create canonical_job_id when a new posting cannot yet be
          linked to an existing CanonicalJob;

        - preserve the existing canonical_job_id during same-source
          upsert;

        - derive first_seen_at and last_seen_at from observation
          lifecycle;

        - calculate persistence-owned hashes deterministically;

        - store a RawJob observation only when it differs from the
          immediately previous persisted observation in arrival order,
          regardless of fetched_at chronology;

        - preserve raw provenance;

        - perform the entire persistence operation atomically;

        - roll back the entire operation on failure.
        """
        ...
