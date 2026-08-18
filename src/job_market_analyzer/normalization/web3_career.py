"""Normalize source-native Web3.career payloads into durable posting input."""

import re
from datetime import UTC, datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.web3_career import (
    WEB3_CAREER_SOURCE_PROVIDER,
    WEB3_CAREER_SOURCE_SCOPE,
)
from job_market_analyzer.models import (
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
)
from job_market_analyzer.normalization.jobs import NormalizationError, html_to_text


class Web3CareerNormalizationError(NormalizationError):
    """Raised when a Web3.career raw job cannot be normalized safely."""


def normalize_web3_career_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Normalize one Web3.career observation without inventing missing values."""

    if (
        raw_job.source_provider != WEB3_CAREER_SOURCE_PROVIDER
        or raw_job.source_scope != WEB3_CAREER_SOURCE_SCOPE
    ):
        raise Web3CareerNormalizationError(
            "RawJob is not from the Web3.career global source"
        )

    payload = raw_job.payload
    payload_id = _required_source_id(payload.get("id"))
    if payload_id != raw_job.external_id:
        raise Web3CareerNormalizationError(
            "Web3.career payload id does not match RawJob external_id"
        )
    _validate_source_url(raw_job, payload.get("url"))

    title = _required_text(payload.get("title"), field_name="title")
    company_name = _optional_text(payload.get("company"), field_name="company")
    location_text = _location_text(payload)
    description_html = _optional_text(
        payload.get("description"),
        field_name="description",
    )
    application_url = _application_url(payload.get("apply_url"))
    is_remote = _is_remote(payload)
    salary_text = _optional_text(payload.get("salary"), field_name="salary")

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        application_url=application_url,
        title=title,
        company_name=company_name,
        description_text=html_to_text(description_html),
        location_text=location_text,
        is_remote=is_remote,
        remote_scope=_remote_scope(payload, location_text, is_remote),
        employment_type=None,
        salary_text=salary_text,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        published_at=_published_at(payload),
        source_updated_at=None,
    )


def _required_source_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise Web3CareerNormalizationError(
            "Web3.career payload field 'id' must be a string or integer"
        )

    external_id = str(value).strip()
    if not external_id:
        raise Web3CareerNormalizationError(
            "Web3.career payload field 'id' must not be blank"
        )
    return external_id


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value, field_name=field_name)
    if text is None:
        raise Web3CareerNormalizationError(
            f"Web3.career payload field '{field_name}' is required"
        )
    return text


def _optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise Web3CareerNormalizationError(
            f"Web3.career payload field '{field_name}' must be a string"
        )
    return value.strip() or None


def _validate_source_url(raw_job: RawJob, value: object) -> None:
    source_url = _optional_text(value, field_name="url")
    if source_url is None:
        if raw_job.source_url is not None:
            raise Web3CareerNormalizationError(
                "Web3.career url does not match RawJob source_url"
            )
        return

    try:
        normalized_source_url = HttpUrl(source_url)
    except ValueError as exc:
        raise Web3CareerNormalizationError(
            "Web3.career payload field 'url' must be an HTTP URL"
        ) from exc

    if normalized_source_url != raw_job.source_url:
        raise Web3CareerNormalizationError(
            "Web3.career url does not match RawJob source_url"
        )


def _application_url(value: object) -> str:
    application_url = _required_text(value, field_name="apply_url")
    try:
        HttpUrl(application_url)
    except ValueError as exc:
        raise Web3CareerNormalizationError(
            "Web3.career payload field 'apply_url' must be an HTTP URL"
        ) from exc
    return application_url


def _location_text(payload: dict[str, object]) -> str | None:
    location = _optional_text(payload.get("location"), field_name="location")
    if location is not None:
        return location

    city = _optional_text(payload.get("city"), field_name="city")
    country = _optional_text(payload.get("country"), field_name="country")
    return ", ".join(part for part in (city, country) if part is not None) or None


def _is_remote(payload: dict[str, object]) -> bool | None:
    values = [
        payload[field_name]
        for field_name in ("is_remote", "remote")
        if field_name in payload and payload[field_name] is not None
    ]
    if not values:
        return None
    if any(not isinstance(value, bool) for value in values):
        raise Web3CareerNormalizationError(
            "Web3.career remote field must be a boolean"
        )
    if len(set(values)) > 1:
        raise Web3CareerNormalizationError(
            "Web3.career remote fields contain conflicting values"
        )
    return values[0]


def _remote_scope(
    payload: dict[str, object],
    location_text: str | None,
    is_remote: bool | None,
) -> RemoteScope | None:
    if is_remote is not True:
        return None
    if _optional_text(payload.get("country"), field_name="country") is not None:
        return RemoteScope.COUNTRY
    if location_text is not None and location_text.casefold() in {
        "anywhere",
        "global",
        "worldwide",
    }:
        return RemoteScope.WORLDWIDE
    return RemoteScope.UNSPECIFIED


def _published_at(payload: dict[str, object]) -> datetime | None:
    for field_name in ("date", "postedAt"):
        parsed_datetime = _parse_datetime(payload.get(field_name))
        if parsed_datetime is not None:
            return parsed_datetime

    return _parse_epoch(payload.get("date_epoch"))


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    date_value = value.strip()
    try:
        parsed_datetime = datetime.fromisoformat(date_value)
    except ValueError:
        return None

    if parsed_datetime.tzinfo is not None and parsed_datetime.utcoffset() is not None:
        return parsed_datetime
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        return parsed_datetime.replace(tzinfo=UTC)
    return None


def _parse_epoch(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None
