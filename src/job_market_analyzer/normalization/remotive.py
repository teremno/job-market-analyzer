"""Normalize public Remotive API jobs into durable posting input."""

from datetime import UTC, datetime

from pydantic import HttpUrl

from job_market_analyzer.collectors.remotive import (
    REMOTIVE_SOURCE_PROVIDER,
    REMOTIVE_SOURCE_SCOPE,
)
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import NormalizationError, html_to_text


class RemotiveNormalizationError(NormalizationError):
    """Raised when a Remotive raw job cannot be normalized safely."""


def normalize_remotive_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map one attributed Remotive observation without extra inference."""

    if (
        raw_job.source_provider != REMOTIVE_SOURCE_PROVIDER
        or raw_job.source_scope != REMOTIVE_SOURCE_SCOPE
    ):
        raise RemotiveNormalizationError("RawJob is not from Remotive global")
    payload = raw_job.payload
    payload_id = _required_id(payload.get("id"))
    source_url = _required_text(payload.get("url"), "url")
    if payload_id != raw_job.external_id or HttpUrl(source_url) != raw_job.source_url:
        raise RemotiveNormalizationError(
            "Remotive payload identity does not match RawJob"
        )
    location = _optional_text(
        payload.get("candidate_required_location"),
        "candidate_required_location",
    )
    category = _optional_text(payload.get("category"), "category")
    tags = _string_list(payload.get("tags"), "tags")
    salary_text = _optional_text(payload.get("salary"), "salary")
    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        application_url=None,
        title=_required_text(payload.get("title"), "title"),
        company_name=_optional_text(payload.get("company_name"), "company_name"),
        description_text=html_to_text(
            _optional_text(payload.get("description"), "description")
        ),
        source_tags=normalize_source_tags(
            (*tags, *((category,) if category is not None else ()))
        ),
        location_text=location,
        is_remote=True,
        remote_scope=_remote_scope(location),
        employment_type=_employment_type(payload.get("job_type")),
        salary_text=salary_text,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        published_at=_publication_datetime(payload.get("publication_date")),
        source_updated_at=None,
    )


def _required_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise RemotiveNormalizationError(
            "Remotive field 'id' must be a string or integer"
        )
    text = str(value).strip()
    if not text:
        raise RemotiveNormalizationError("Remotive field 'id' must not be blank")
    return text


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise RemotiveNormalizationError(
            f"Remotive field '{field_name}' is required"
        )
    return text


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RemotiveNormalizationError(
            f"Remotive field '{field_name}' must be a string"
        )
    return value.strip() or None


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RemotiveNormalizationError(
            f"Remotive field '{field_name}' must be an array of strings"
        )
    return tuple(item.strip() for item in value if item.strip())


def _publication_datetime(value: object) -> datetime | None:
    text = _optional_text(value, "publication_date")
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RemotiveNormalizationError(
            "Remotive field 'publication_date' must be an ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _remote_scope(location: str | None) -> RemoteScope:
    if location is None:
        return RemoteScope.UNSPECIFIED
    if location.casefold() in {"anywhere", "global", "worldwide"}:
        return RemoteScope.WORLDWIDE
    return RemoteScope.REGION


def _employment_type(value: object) -> EmploymentType | None:
    text = _optional_text(value, "job_type")
    if text is None:
        return None
    return {
        "full time": EmploymentType.FULL_TIME,
        "part time": EmploymentType.PART_TIME,
        "contract": EmploymentType.CONTRACT,
        "freelance": EmploymentType.FREELANCE,
        "internship": EmploymentType.INTERNSHIP,
        "temporary": EmploymentType.TEMPORARY,
    }.get(text.casefold().replace("-", " ").replace("_", " "))
