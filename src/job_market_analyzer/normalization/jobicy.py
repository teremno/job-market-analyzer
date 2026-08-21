"""Normalize public Jobicy API jobs into durable posting input."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import unescape

from pydantic import HttpUrl

from job_market_analyzer.collectors.jobicy import (
    JOBICY_SOURCE_PROVIDER,
    JOBICY_SOURCE_SCOPE,
)
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    SalaryPeriod,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import NormalizationError, html_to_text


class JobicyNormalizationError(NormalizationError):
    """Raised when a Jobicy raw job cannot be normalized safely."""


def normalize_jobicy_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map one Jobicy observation without fabricating absent fields."""

    if (
        raw_job.source_provider != JOBICY_SOURCE_PROVIDER
        or raw_job.source_scope != JOBICY_SOURCE_SCOPE
    ):
        raise JobicyNormalizationError("RawJob is not from Jobicy global")
    payload = raw_job.payload
    payload_id = _required_id(payload.get("id"))
    source_url = _required_text(payload.get("url"), "url")
    if payload_id != raw_job.external_id or HttpUrl(source_url) != raw_job.source_url:
        raise JobicyNormalizationError("Jobicy payload identity does not match RawJob")
    job_types = _string_list(payload.get("jobType"), "jobType")
    industries = tuple(
        unescape(item) for item in _string_list(payload.get("jobIndustry"), "jobIndustry")
    )
    salary_min = _decimal(payload.get("salaryMin"), "salaryMin")
    salary_max = _decimal(payload.get("salaryMax"), "salaryMax")
    currency = _optional_text(payload.get("salaryCurrency"), "salaryCurrency")
    period = _salary_period(payload.get("salaryPeriod"))
    if salary_min is None and salary_max is None:
        currency = None
        period = None
    location = _optional_text(payload.get("jobGeo"), "jobGeo")
    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        application_url=None,
        title=unescape(_required_text(payload.get("jobTitle"), "jobTitle")),
        company_name=_unescaped_optional(payload.get("companyName"), "companyName"),
        description_text=html_to_text(
            _optional_text(payload.get("jobDescription"), "jobDescription")
        ),
        source_tags=normalize_source_tags(industries),
        location_text=location,
        is_remote=True,
        remote_scope=_remote_scope(location),
        employment_type=_employment_type(job_types),
        salary_text=None,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_period=period,
        published_at=_iso_datetime(payload.get("pubDate"), "pubDate"),
        source_updated_at=None,
    )


def _required_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise JobicyNormalizationError("Jobicy field 'id' must be a string or integer")
    text = str(value).strip()
    if not text:
        raise JobicyNormalizationError("Jobicy field 'id' must not be blank")
    return text


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise JobicyNormalizationError(f"Jobicy field '{field_name}' is required")
    return text


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise JobicyNormalizationError(
            f"Jobicy field '{field_name}' must be a string"
        )
    return value.strip() or None


def _unescaped_optional(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    return unescape(text) if text is not None else None


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise JobicyNormalizationError(
            f"Jobicy field '{field_name}' must be an array of strings"
        )
    return tuple(item.strip() for item in value if item.strip())


def _decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise JobicyNormalizationError(f"Jobicy field '{field_name}' must be numeric")
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise JobicyNormalizationError(
            f"Jobicy field '{field_name}' must be numeric"
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise JobicyNormalizationError(
            f"Jobicy field '{field_name}' must be a non-negative finite number"
        )
    return parsed


def _iso_datetime(value: object, field_name: str) -> datetime | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise JobicyNormalizationError(
            f"Jobicy field '{field_name}' must be an ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise JobicyNormalizationError(
            f"Jobicy field '{field_name}' must include a timezone"
        )
    return parsed


def _remote_scope(location: str | None) -> RemoteScope:
    if location is None:
        return RemoteScope.UNSPECIFIED
    if location.casefold() in {"anywhere", "global", "worldwide"}:
        return RemoteScope.WORLDWIDE
    return RemoteScope.REGION


def _employment_type(values: tuple[str, ...]) -> EmploymentType | None:
    if len(values) != 1:
        return None
    return {
        "full time": EmploymentType.FULL_TIME,
        "part time": EmploymentType.PART_TIME,
        "contract": EmploymentType.CONTRACT,
        "freelance": EmploymentType.FREELANCE,
        "internship": EmploymentType.INTERNSHIP,
        "temporary": EmploymentType.TEMPORARY,
    }.get(values[0].casefold().replace("-", " "))


def _salary_period(value: object) -> SalaryPeriod | None:
    text = _optional_text(value, "salaryPeriod")
    if text is None:
        return None
    return {
        "yearly": SalaryPeriod.YEARLY,
        "annual": SalaryPeriod.YEARLY,
        "monthly": SalaryPeriod.MONTHLY,
        "weekly": SalaryPeriod.WEEKLY,
        "daily": SalaryPeriod.DAILY,
        "hourly": SalaryPeriod.HOURLY,
    }.get(text.casefold())
