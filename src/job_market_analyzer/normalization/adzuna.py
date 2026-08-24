"""Normalize public Adzuna postings into durable posting input."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from pydantic import HttpUrl

from job_market_analyzer.collectors.adzuna import (
    ADZUNA_SOURCE_PROVIDER,
    COUNTRY_CURRENCY,
)
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    SalaryPeriod,
    normalize_source_tags,
)


class AdzunaNormalizationError(ValueError):
    """Raised when an Adzuna raw posting cannot be normalized safely."""


_CONTRACT_TYPES = {
    "contract": EmploymentType.CONTRACT,
    "permanent": EmploymentType.FULL_TIME,
    "full_time": EmploymentType.FULL_TIME,
    "part_time": EmploymentType.PART_TIME,
}


def normalize_adzuna_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map search-result fields without inventing salary or remote data."""

    if raw_job.source_provider != ADZUNA_SOURCE_PROVIDER:
        raise AdzunaNormalizationError("RawJob is not from Adzuna")
    payload = raw_job.payload
    external_id = _required_id(payload.get("id"))
    if external_id != raw_job.external_id:
        raise AdzunaNormalizationError("Adzuna id does not match RawJob identity")

    salary_min, salary_max, salary_currency, salary_period = _salary_fields(payload, raw_job.source_scope)

    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=_optional_url(payload.get("redirect_url"), "redirect_url"),
        application_url=_optional_url(payload.get("redirect_url"), "redirect_url"),
        title=_required_text(payload.get("title"), "title"),
        company_name=_company_name(payload.get("company")),
        description_text=_plain_description(payload.get("description")),
        source_tags=normalize_source_tags(_category_label(payload)),
        location_text=_location_text(payload.get("location")),
        is_remote=None,
        remote_scope=None,
        employment_type=_employment_type(payload.get("contract_type")),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_period=salary_period,
        published_at=_aware_datetime(payload.get("created"), "created"),
        source_updated_at=None,
    )


def _salary_fields(
    payload: dict[str, object], source_scope: str
) -> tuple[Decimal | None, Decimal | None, str | None]:
    """Return actual advertised salaries; Adzuna-predicted values are skipped.

    Currency is mapped from the country scope (Adzuna GB results are GBP,
    US results are USD) rather than guessed from text.
    """

    if str(payload.get("salary_is_predicted", "0")) != "0":
        return (None, None, None, None)
    minimum = _optional_decimal(payload.get("salary_min"))
    maximum = _optional_decimal(payload.get("salary_max"))
    if minimum is None and maximum is None:
        return (None, None, None, None)
    currency = COUNTRY_CURRENCY.get(source_scope)
    return (minimum, maximum, currency, SalaryPeriod.YEARLY)


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def _company_name(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AdzunaNormalizationError("Adzuna field 'company' must be an object")
    name = value.get("display_name")
    if name is None:
        return None
    if not isinstance(name, str):
        raise AdzunaNormalizationError(
            "Adzuna field 'company.display_name' must be a string"
        )
    return name.strip() or None


def _category_label(payload: dict[str, object]) -> tuple[str, ...]:
    category = payload.get("category")
    if not isinstance(category, dict):
        return ()
    label = category.get("label")
    if isinstance(label, str) and label.strip():
        return (label.strip(),)
    return ()


def _location_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AdzunaNormalizationError("Adzuna field 'location' must be an object")
    name = value.get("display_name")
    if name is None:
        return None
    if not isinstance(name, str):
        raise AdzunaNormalizationError(
            "Adzuna field 'location.display_name' must be a string"
        )
    return name.strip() or None


def _plain_description(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdzunaNormalizationError(
            "Adzuna field 'description' must be a string"
        )
    return value.strip() or None


def _employment_type(value: object) -> EmploymentType | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    return _CONTRACT_TYPES.get(value.strip().casefold())


_CONTRACT_TYPES = {
    "contract": EmploymentType.CONTRACT,
    "permanent": EmploymentType.FULL_TIME,
    "full_time": EmploymentType.FULL_TIME,
    "part_time": EmploymentType.PART_TIME,
}


def _aware_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' must be an ISO datetime string"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' must include a timezone offset"
        )
    return parsed


def _required_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise AdzunaNormalizationError(
            "Adzuna field 'id' must be a string or integer"
        )
    text = str(value).strip()
    if not text:
        raise AdzunaNormalizationError("Adzuna field 'id' must not be blank")
    return text


def _required_text(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' must be a string or integer"
        )
    text = str(value).strip()
    if not text:
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' is required"
        )
    return text


def _optional_url(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' must be a string"
        )
    text = value.strip()
    if not text:
        return None
    try:
        HttpUrl(text)
    except ValueError as exc:
        raise AdzunaNormalizationError(
            f"Adzuna field '{field_name}' must be an HTTP URL"
        ) from exc
    return text
