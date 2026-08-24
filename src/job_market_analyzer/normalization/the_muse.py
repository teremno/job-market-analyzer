"""Normalize public The Muse postings into durable posting input."""

from datetime import datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.the_muse import THE_MUSE_SOURCE_PROVIDER
from job_market_analyzer.models import (
    NormalizedJobPosting,
    RawJob,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import html_to_text


class TheMuseNormalizationError(ValueError):
    """Raised when a The Muse raw posting cannot be normalized safely."""


def normalize_the_muse_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map public listing fields without inventing salary or remote data."""

    if raw_job.source_provider != THE_MUSE_SOURCE_PROVIDER:
        raise TheMuseNormalizationError("RawJob is not from The Muse")
    payload = raw_job.payload
    external_id = _required_text(payload.get("id"), "id")
    if external_id != raw_job.external_id:
        raise TheMuseNormalizationError(
            "The Muse id does not match RawJob identity"
        )

    landing_page = _optional_url(_landing_page(payload.get("refs")), "refs.landing_page")

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=landing_page,
        application_url=landing_page,
        title=_required_text(payload.get("name"), "name"),
        company_name=_company_name(payload.get("company")),
        description_text=html_to_text(
            _optional_text(payload.get("contents"), "contents")
        ),
        source_tags=normalize_source_tags(_observed_labels(payload)),
        location_text=_location_text(payload.get("locations")),
        is_remote=None,
        remote_scope=None,
        employment_type=None,
        salary_text=None,
        published_at=_aware_datetime(
            payload.get("publication_date"), "publication_date"
        ),
        source_updated_at=None,
    )


def _landing_page(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TheMuseNormalizationError("The Muse field 'refs' must be an object")
    landing = value.get("landing_page")
    if landing is None:
        return None
    if not isinstance(landing, str):
        raise TheMuseNormalizationError(
            "The Muse field 'refs.landing_page' must be a string"
        )
    return landing.strip() or None


def _company_name(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TheMuseNormalizationError("The Muse field 'company' must be an object")
    name = value.get("name")
    if name is None:
        return None
    text = name.strip()
    if not isinstance(name, str):
        raise TheMuseNormalizationError(
            "The Muse field 'company.name' must be a string"
        )
    return text or None


def _observed_labels(payload: dict[str, object]) -> tuple[str, ...]:
    labels: list[str] = []
    for field_name in ("categories", "levels"):
        value = payload.get(field_name)
        if value is None:
            continue
        if not isinstance(value, list):
            raise TheMuseNormalizationError(
                f"The Muse field '{field_name}' must be an array"
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
    if not isinstance(value, list):
        raise TheMuseNormalizationError(
            "The Muse field 'locations' must be an array"
        )
    names: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            name = item["name"].strip()
            if name:
                names.append(name)
    return ", ".join(names) or None


def _aware_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' must be an ISO datetime string"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' must include a timezone offset"
        )
    return parsed


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' must be a string"
        )
    text = value.strip()
    return text or None


def _required_text(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' must be a string or integer"
        )
    text = str(value).strip()
    if not text:
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' is required"
        )
    return text


def _optional_url(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        HttpUrl(text)
    except ValueError as exc:
        raise TheMuseNormalizationError(
            f"The Muse field '{field_name}' must be an HTTP URL"
        ) from exc
    return text
