"""Normalize official We Work Remotely RSS items into posting input."""

from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape

from pydantic import HttpUrl

from job_market_analyzer.collectors.we_work_remotely import (
    WE_WORK_REMOTELY_SOURCE_PROVIDER,
    WE_WORK_REMOTELY_SOURCE_SCOPE,
)
from job_market_analyzer.models import (
    EmploymentType,
    NormalizedJobPosting,
    RawJob,
    RemoteScope,
    normalize_source_tags,
)
from job_market_analyzer.normalization.jobs import NormalizationError, html_to_text


class WeWorkRemotelyNormalizationError(NormalizationError):
    """Raised when a WWR RSS item cannot be normalized safely."""


def normalize_we_work_remotely_job(raw_job: RawJob) -> NormalizedJobPosting:
    """Map one WWR RSS observation without scraping its linked page."""

    if (
        raw_job.source_provider != WE_WORK_REMOTELY_SOURCE_PROVIDER
        or raw_job.source_scope != WE_WORK_REMOTELY_SOURCE_SCOPE
    ):
        raise WeWorkRemotelyNormalizationError(
            "RawJob is not from We Work Remotely global"
        )
    payload = raw_job.payload
    guid = _required_text(payload.get("guid"), "guid")
    link = _required_text(payload.get("link"), "link")
    if guid != raw_job.external_id or HttpUrl(link) != raw_job.source_url:
        raise WeWorkRemotelyNormalizationError(
            "We Work Remotely payload identity does not match RawJob"
        )
    title_text = unescape(_required_text(payload.get("title"), "title"))
    company_name, title = _split_title(title_text)
    region = _optional_text(payload.get("region"), "region")
    country = _optional_text(payload.get("country"), "country")
    state = _optional_text(payload.get("state"), "state")
    location_parts = tuple(
        dict.fromkeys(part for part in (region, country, state) if part is not None)
    )
    category = _optional_text(payload.get("category"), "category")
    skills = _optional_text(payload.get("skills"), "skills")
    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        application_url=None,
        title=title,
        company_name=company_name,
        description_text=html_to_text(
            _optional_text(payload.get("description"), "description")
        ),
        source_tags=normalize_source_tags(
            tuple(value for value in (category, skills) if value is not None)
        ),
        location_text=", ".join(location_parts) or None,
        is_remote=True,
        remote_scope=_remote_scope(region),
        employment_type=_employment_type(payload.get("type")),
        salary_text=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        published_at=_rfc_datetime(payload.get("pubDate"), "pubDate"),
        source_updated_at=None,
    )


def _split_title(value: str) -> tuple[str | None, str]:
    company, separator, title = value.partition(": ")
    if separator and company.strip() and title.strip():
        return company.strip(), title.strip()
    return None, value


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value, field_name)
    if text is None:
        raise WeWorkRemotelyNormalizationError(
            f"We Work Remotely field '{field_name}' is required"
        )
    return text


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise WeWorkRemotelyNormalizationError(
            f"We Work Remotely field '{field_name}' must be a string"
        )
    return value.strip() or None


def _rfc_datetime(value: object, field_name: str) -> datetime | None:
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError) as exc:
        raise WeWorkRemotelyNormalizationError(
            f"We Work Remotely field '{field_name}' must be an RFC datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WeWorkRemotelyNormalizationError(
            f"We Work Remotely field '{field_name}' must include a timezone"
        )
    return parsed


def _remote_scope(region: str | None) -> RemoteScope:
    if region is None:
        return RemoteScope.UNSPECIFIED
    if region.casefold() in {"anywhere", "anywhere in the world", "worldwide"}:
        return RemoteScope.WORLDWIDE
    return RemoteScope.REGION


def _employment_type(value: object) -> EmploymentType | None:
    text = _optional_text(value, "type")
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
