"""Normalize public Ashby postings into durable posting input."""

from datetime import datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.ashby import ASHBY_SOURCE_PROVIDER
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import html_to_text


class AshbyNormalizationError(ValueError):
    """Raised when an Ashby raw posting cannot be normalized safely."""


_EMPLOYMENT_TYPES = {
    "fulltime": EmploymentType.FULL_TIME,
    "full_time": EmploymentType.FULL_TIME,
    "parttime": EmploymentType.PART_TIME,
    "part_time": EmploymentType.PART_TIME,
    "contractor": EmploymentType.CONTRACT,
    "contract": EmploymentType.CONTRACT,
    "internship": EmploymentType.INTERNSHIP,
    "temporary": EmploymentType.TEMPORARY,
}


def normalize_ashby_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map board fields without inventing company or salary data."""

    if raw_job.source_provider != ASHBY_SOURCE_PROVIDER:
        raise AshbyNormalizationError("RawJob is not from Ashby")
    payload = raw_job.payload
    external_id = _required_text(payload.get("id"), "id")
    if external_id != raw_job.external_id:
        raise AshbyNormalizationError("Ashby id does not match RawJob identity")

    is_remote = _optional_bool(payload.get("isRemote"), "isRemote")
    employment_type = _employment_type(
        _optional_text(payload.get("employmentType"), "employmentType")
    )

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=_optional_url(payload.get("jobUrl"), "jobUrl"),
        application_url=_optional_url(payload.get("applyUrl"), "applyUrl"),
        title=_required_text(payload.get("title"), "title"),
        company_name=None,
        description_text=_description(payload),
        source_tags=normalize_source_tags(_observed_labels(payload)),
        location_text=_optional_text(payload.get("location"), "location"),
        is_remote=is_remote,
        remote_scope=None,
        employment_type=employment_type,
        salary_text=None,
        published_at=_aware_datetime(payload.get("publishedAt"), "publishedAt"),
        source_updated_at=None,
    )


def _description(payload: dict[str, object]) -> str | None:
    plain = _optional_text(payload.get("descriptionPlain"), "descriptionPlain")
    if plain is not None:
        return plain
    return html_to_text(
        _optional_text(payload.get("descriptionHtml"), "descriptionHtml")
    )


def _observed_labels(payload: dict[str, object]) -> tuple[str, ...]:
    labels: list[str] = []
    for field_name in ("department", "team"):
        text = _optional_text(payload.get(field_name), field_name)
        if text is not None:
            labels.append(text)
    return tuple(labels)


def _employment_type(value: str | None) -> EmploymentType | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    employment_type = _EMPLOYMENT_TYPES.get(normalized)
    if employment_type is None:
        # Unknown labels are not invented into a category; the raw payload
        # remains provenance for later revisions.
        return None
    return employment_type


def _optional_bool(value: object, field_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise AshbyNormalizationError(f"Ashby field '{field_name}' must be boolean")
    return value


def _aware_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AshbyNormalizationError(
            f"Ashby field '{field_name}' must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise AshbyNormalizationError(
            f"Ashby field '{field_name}' must be an ISO datetime string"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AshbyNormalizationError(
            f"Ashby field '{field_name}' must include a timezone offset"
        )
    return parsed


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AshbyNormalizationError(f"Ashby field '{field_name}' must be a string")
    text = value.strip()
    return text or None


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise AshbyNormalizationError(f"Ashby field '{field_name}' is required")
    return text


def _optional_url(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        HttpUrl(text)
    except ValueError as exc:
        raise AshbyNormalizationError(
            f"Ashby field '{field_name}' must be an HTTP URL"
        ) from exc
    return text
