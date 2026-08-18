"""Normalize source-native Remote OK payloads into durable posting input."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.remote_ok import (
    REMOTE_OK_SOURCE_PROVIDER,
    REMOTE_OK_SOURCE_SCOPE,
)
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import NormalizationError, html_to_text


class RemoteOKNormalizationError(NormalizationError):
    """Raised when a Remote OK raw job cannot be normalized safely."""


def normalize_remote_ok_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Normalize one Remote OK observation without inventing missing values."""

    if (
        raw_job.source_provider != REMOTE_OK_SOURCE_PROVIDER
        or raw_job.source_scope != REMOTE_OK_SOURCE_SCOPE
    ):
        raise RemoteOKNormalizationError(
            "RawJob is not from the Remote OK global source"
        )

    payload = raw_job.payload
    payload_id = _required_source_id(payload.get("id"))
    if payload_id != raw_job.external_id:
        raise RemoteOKNormalizationError(
            "Remote OK payload id does not match RawJob external_id"
        )

    title = _required_text(payload.get("position"), field_name="position")
    company_name = _optional_text(payload.get("company"), field_name="company")
    location_text = _optional_text(payload.get("location"), field_name="location")
    description_html = _optional_text(
        payload.get("description"),
        field_name="description",
    )
    application_url = _application_url(raw_job, payload.get("apply_url"))
    source_tags = normalize_source_tags(payload.get("tags"))

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        application_url=application_url,
        title=title,
        company_name=company_name,
        description_text=html_to_text(description_html),
        source_tags=source_tags,
        location_text=location_text,
        is_remote=True,
        remote_scope=_remote_scope(location_text),
        employment_type=_employment_type(source_tags),
        salary_text=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        published_at=_published_at(payload),
        source_updated_at=None,
    )


def _required_source_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise RemoteOKNormalizationError(
            "Remote OK payload field 'id' must be a string or integer"
        )

    external_id = str(value).strip()
    if not external_id:
        raise RemoteOKNormalizationError(
            "Remote OK payload field 'id' must not be blank"
        )

    return external_id


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value, field_name=field_name)
    if text is None:
        raise RemoteOKNormalizationError(
            f"Remote OK payload field '{field_name}' is required"
        )

    return text


def _optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RemoteOKNormalizationError(
            f"Remote OK payload field '{field_name}' must be a string"
        )

    return value.strip() or None


def _application_url(raw_job: RawJob, value: object) -> str | None:
    application_url = _optional_text(value, field_name="apply_url")
    if application_url is None:
        return None

    try:
        normalized_application_url = HttpUrl(application_url)
    except ValueError as exc:
        raise RemoteOKNormalizationError(
            "Remote OK payload field 'apply_url' must be an HTTP URL"
        ) from exc

    if normalized_application_url == raw_job.source_url:
        return None

    return application_url


def _remote_scope(location_text: str | None) -> RemoteScope:
    if location_text is not None and location_text.casefold() in {
        "anywhere",
        "global",
        "worldwide",
    }:
        return RemoteScope.WORLDWIDE

    return RemoteScope.UNSPECIFIED


def _employment_type(value: tuple[str, ...]) -> EmploymentType | None:
    mappings = {
        "contract": EmploymentType.CONTRACT,
        "freelance": EmploymentType.FREELANCE,
        "full time": EmploymentType.FULL_TIME,
        "internship": EmploymentType.INTERNSHIP,
        "part time": EmploymentType.PART_TIME,
        "temporary": EmploymentType.TEMPORARY,
    }
    matches = {
        mappings[normalized_tag]
        for tag in value
        if (normalized_tag := tag.strip().casefold().replace("-", " ").replace("_", " "))
        in mappings
    }

    if len(matches) == 1:
        return next(iter(matches))

    return None


def _published_at(payload: dict[str, object]) -> datetime | None:
    date_value = _optional_text(payload.get("date"), field_name="date")
    if date_value is not None:
        try:
            published_at = datetime.fromisoformat(date_value)
        except ValueError as exc:
            raise RemoteOKNormalizationError(
                "Remote OK payload field 'date' must be an ISO-8601 datetime"
            ) from exc

        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise RemoteOKNormalizationError(
                "Remote OK payload field 'date' must include a timezone"
            )

        return published_at

    epoch_value = payload.get("epoch")
    if epoch_value is None:
        return None
    if isinstance(epoch_value, bool) or not isinstance(epoch_value, (int, float)):
        raise RemoteOKNormalizationError(
            "Remote OK payload field 'epoch' must be a number"
        )

    try:
        return datetime.fromtimestamp(epoch_value, tz=UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise RemoteOKNormalizationError(
            "Remote OK payload field 'epoch' is outside the supported range"
        ) from exc
