"""Normalize public Himalayas API jobs into durable posting input."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from pydantic import HttpUrl

from job_market_analyzer.collectors.himalayas import (
    HIMALAYAS_SOURCE_PROVIDER,
    HIMALAYAS_SOURCE_SCOPE,
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


class HimalayasNormalizationError(NormalizationError):
    """Raised when a Himalayas raw job cannot be normalized safely."""


def normalize_himalayas_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map source fields without inferring absent salary or role data."""

    _require_source(raw_job)
    payload = raw_job.payload
    guid = _required_text(payload.get("guid"), "guid")
    if guid != raw_job.external_id or HttpUrl(guid) != raw_job.source_url:
        raise HimalayasNormalizationError(
            "Himalayas guid does not match RawJob identity"
        )
    locations = _string_list(payload.get("locationRestrictions"), "locationRestrictions")
    timezones = _number_list(payload.get("timezoneRestrictions"), "timezoneRestrictions")
    categories = _string_list(payload.get("categories"), "categories")
    parent_categories = _string_list(
        payload.get("parentCategories"), "parentCategories"
    )
    salary_min = _decimal(payload.get("minSalary"), "minSalary")
    salary_max = _decimal(payload.get("maxSalary"), "maxSalary")
    currency = _optional_text(payload.get("currency"), "currency")
    period = _salary_period(payload.get("salaryPeriod"))
    if salary_min is None and salary_max is None:
        currency = None
        period = None

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        application_url=_optional_url(payload.get("applicationLink"), "applicationLink"),
        title=_required_text(payload.get("title"), "title"),
        company_name=_optional_text(payload.get("companyName"), "companyName"),
        description_text=html_to_text(
            _optional_text(payload.get("description"), "description")
        ),
        source_tags=normalize_source_tags((*categories, *parent_categories)),
        location_text=", ".join(locations) or None,
        is_remote=True,
        remote_scope=_remote_scope(locations, timezones),
        employment_type=_employment_type(payload.get("employmentType")),
        salary_text=None,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_period=period,
        published_at=_epoch_datetime(payload.get("pubDate"), "pubDate"),
        source_updated_at=None,
    )


def _require_source(raw_job: RawJob) -> None:
    if (
        raw_job.source_provider != HIMALAYAS_SOURCE_PROVIDER
        or raw_job.source_scope != HIMALAYAS_SOURCE_SCOPE
    ):
        raise HimalayasNormalizationError("RawJob is not from Himalayas global")


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' is required"
        )
    return text


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be a string"
        )
    return value.strip() or None


def _optional_url(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        HttpUrl(text)
    except ValueError as exc:
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be an HTTP URL"
        ) from exc
    return text


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be an array of strings"
        )
    return tuple(item.strip() for item in value if item.strip())


def _number_list(value: object, field_name: str) -> tuple[Decimal, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) for item in value
    ):
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be an array of numbers"
        )
    return tuple(Decimal(str(item)) for item in value)


def _decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be numeric"
        )
    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be numeric"
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be a non-negative finite number"
        )
    return parsed


def _epoch_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' must be an epoch number"
        )
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise HimalayasNormalizationError(
            f"Himalayas field '{field_name}' is outside the supported range"
        ) from exc


def _remote_scope(
    locations: tuple[str, ...], timezones: tuple[Decimal, ...]
) -> RemoteScope:
    if any(value.casefold() in {"anywhere", "worldwide"} for value in locations):
        return RemoteScope.WORLDWIDE
    if timezones:
        return RemoteScope.TIMEZONE
    if locations:
        return RemoteScope.REGION
    return RemoteScope.UNSPECIFIED


def _employment_type(value: object) -> EmploymentType | None:
    text = _optional_text(value, "employmentType")
    if text is None:
        return None
    return {
        "full time": EmploymentType.FULL_TIME,
        "part time": EmploymentType.PART_TIME,
        "contract": EmploymentType.CONTRACT,
        "freelance": EmploymentType.FREELANCE,
        "internship": EmploymentType.INTERNSHIP,
        "temporary": EmploymentType.TEMPORARY,
    }.get(text.casefold().replace("-", " "))


def _salary_period(value: object) -> SalaryPeriod | None:
    text = _optional_text(value, "salaryPeriod")
    if text is None:
        return None
    return {
        "annual": SalaryPeriod.YEARLY,
        "yearly": SalaryPeriod.YEARLY,
        "monthly": SalaryPeriod.MONTHLY,
        "weekly": SalaryPeriod.WEEKLY,
        "daily": SalaryPeriod.DAILY,
        "hourly": SalaryPeriod.HOURLY,
    }.get(text.casefold())
