"""Normalize public Greenhouse job board postings into durable posting input."""

from datetime import datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.greenhouse import GREENHOUSE_SOURCE_PROVIDER
from job_market_analyzer.models import (
    NormalizedJobPosting,
    RawJob,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import NormalizationError, html_to_text


class GreenhouseNormalizationError(NormalizationError):
    """Raised when a Greenhouse raw job cannot be normalized safely."""


def normalize_greenhouse_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map board fields without inferring absent salary or remote data."""

    _require_source(raw_job)
    payload = raw_job.payload
    external_id = _required_identity(payload.get("id"))
    if external_id != raw_job.external_id:
        raise GreenhouseNormalizationError(
            "Greenhouse id does not match RawJob identity"
        )

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=_optional_url(payload.get("absolute_url"), "absolute_url"),
        application_url=_optional_url(payload.get("absolute_url"), "absolute_url"),
        title=_required_text(payload.get("title"), "title"),
        company_name=_optional_text(
            payload.get("company_name"), "company_name"
        ),
        description_text=html_to_text(
            _optional_text(payload.get("content"), "content")
        ),
        source_tags=normalize_source_tags(_observed_labels(payload)),
        location_text=_location_text(payload.get("location")),
        is_remote=None,
        remote_scope=None,
        employment_type=None,
        salary_text=None,
        published_at=_aware_datetime(payload.get("first_published"), "first_published"),
        source_updated_at=_aware_datetime(payload.get("updated_at"), "updated_at"),
    )


def _require_source(raw_job: RawJob) -> None:
    if raw_job.source_provider != GREENHOUSE_SOURCE_PROVIDER:
        raise GreenhouseNormalizationError("RawJob is not from Greenhouse")
    if not raw_job.source_scope.strip():
        raise GreenhouseNormalizationError(
            "Greenhouse source scope must be a board token"
        )


def _observed_labels(payload: dict[str, object]) -> tuple[str, ...]:
    """Collect department and office names as structured source-observed labels."""

    labels: list[str] = []
    for field_name in ("departments", "offices"):
        value = payload.get(field_name)
        if value is None:
            continue
        if not isinstance(value, list):
            raise GreenhouseNormalizationError(
                f"Greenhouse field '{field_name}' must be an array"
            )
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                name = item["name"].strip()
                if name:
                    labels.append(name)
    return tuple(labels)


def _location_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise GreenhouseNormalizationError(
            "Greenhouse field 'location' must be an object"
        )
    name = value.get("name")
    if name is None:
        return None
    text = _optional_text(name, "location.name")
    return text


def _aware_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GreenhouseNormalizationError(
            f"Greenhouse field '{field_name}' must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise GreenhouseNormalizationError(
            f"Greenhouse field '{field_name}' must be an ISO datetime string"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GreenhouseNormalizationError(
            f"Greenhouse field '{field_name}' must include a timezone offset"
        )
    return parsed


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GreenhouseNormalizationError(
            f"Greenhouse field '{field_name}' must be a string"
        )
    text = value.strip()
    return text or None


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise GreenhouseNormalizationError(
            f"Greenhouse field '{field_name}' is required"
        )
    return text


def _required_identity(value: object) -> str:
    """Accept string or integer native ids without accepting booleans."""

    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise GreenhouseNormalizationError(
            "Greenhouse field 'id' must be a string or integer"
        )
    text = str(value).strip()
    if not text:
        raise GreenhouseNormalizationError(
            "Greenhouse field 'id' must not be blank"
        )
    return text


def _optional_url(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        HttpUrl(text)
    except ValueError as exc:
        raise GreenhouseNormalizationError(
            f"Greenhouse field '{field_name}' must be an HTTP URL"
        ) from exc
    return text
