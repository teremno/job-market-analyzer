"""Normalize public Lever postings into durable posting input."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.lever import LEVER_SOURCE_PROVIDER
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import html_to_text


class LeverNormalizationError(ValueError):
    """Raised when a Lever raw posting cannot be normalized safely."""


_EMPLOYMENT_TYPES = {
    "full time": EmploymentType.FULL_TIME,
    "full-time": EmploymentType.FULL_TIME,
    "permanent": EmploymentType.FULL_TIME,
    "part time": EmploymentType.PART_TIME,
    "part-time": EmploymentType.PART_TIME,
    "contract": EmploymentType.CONTRACT,
    "contractor": EmploymentType.CONTRACT,
    "freelance": EmploymentType.FREELANCE,
    "internship": EmploymentType.INTERNSHIP,
    "apprenticeship": EmploymentType.INTERNSHIP,
    "temporary": EmploymentType.TEMPORARY,
}


def normalize_lever_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map board fields without inventing company or salary data."""

    if raw_job.source_provider != LEVER_SOURCE_PROVIDER:
        raise LeverNormalizationError("RawJob is not from Lever")
    payload = raw_job.payload
    external_id = _required_text(payload.get("id"), "id")
    if external_id != raw_job.external_id:
        raise LeverNormalizationError("Lever id does not match RawJob identity")

    categories = _mapping(payload.get("categories"), "categories")
    commitment = _optional_text(categories.get("commitment"), "commitment")
    workplace_type = _optional_text(payload.get("workplaceType"), "workplaceType")

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=_optional_url(payload.get("hostedUrl"), "hostedUrl"),
        application_url=_optional_url(payload.get("applyUrl"), "applyUrl"),
        title=_required_text(payload.get("text"), "text"),
        company_name=None,
        description_text=_description(payload),
        source_tags=normalize_source_tags(_observed_labels(categories)),
        location_text=_optional_text(
            categories.get("location"), "categories.location"
        ),
        is_remote=_is_remote(workplace_type, "workplaceType"),
        remote_scope=None,
        employment_type=_employment_type(commitment),
        salary_text=None,
        published_at=_epoch_datetime(payload.get("createdAt"), "createdAt"),
        source_updated_at=None,
    )


def _description(payload: dict[str, object]) -> str | None:
    plain = _optional_text(payload.get("descriptionPlain"), "descriptionPlain")
    if plain is not None:
        return plain
    return html_to_text(_optional_text(payload.get("description"), "description"))


def _observed_labels(categories: dict[str, object]) -> tuple[str, ...]:
    labels: list[str] = []
    for field_name in ("department", "team"):
        text = _optional_text(categories.get(field_name), f"categories.{field_name}")
        if text is not None:
            labels.append(text)
    return tuple(labels)


def _mapping(value: object, field_name: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise LeverNormalizationError(f"Lever field '{field_name}' must be an object")
    return value


def _employment_type(value: str | None) -> EmploymentType | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    employment_type = _EMPLOYMENT_TYPES.get(normalized)
    if employment_type is None:
        # Unknown commitment labels are preserved nowhere and invented nowhere;
        # the raw payload remains the provenance for later revisions.
        return None
    return employment_type


def _is_remote(workplace_type: str | None, field_name: str) -> bool | None:
    if workplace_type is None:
        return None
    normalized = workplace_type.strip().casefold()
    if normalized == "remote":
        return True
    if normalized in {"hybrid", "onsite", "on-site", "in-office"}:
        return False
    raise LeverNormalizationError(
        f"Lever field '{field_name}' has an unsupported value"
    )


def _epoch_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LeverNormalizationError(
            f"Lever field '{field_name}' must be an epoch number"
        )
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise LeverNormalizationError(
            f"Lever field '{field_name}' is outside the supported range"
        ) from exc


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LeverNormalizationError(f"Lever field '{field_name}' must be a string")
    text = value.strip()
    return text or None


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise LeverNormalizationError(f"Lever field '{field_name}' is required")
    return text


def _optional_url(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        HttpUrl(text)
    except ValueError as exc:
        raise LeverNormalizationError(
            f"Lever field '{field_name}' must be an HTTP URL"
        ) from exc
    return text
