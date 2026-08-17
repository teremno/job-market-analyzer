from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class RawJob(BaseModel):
    """A job listing exactly as collected from an external source."""

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)

    title: str = Field(min_length=1)

    fetched_at: datetime

    payload: dict[str, Any]



class JobPosting(BaseModel):
    """Normalized job posting from one specific source."""

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)

    title: str = Field(min_length=1)
    company_name: str | None = None
    description_text: str | None = None

    location_text: str | None = None
    is_remote: bool | None = None
    remote_scope: str | None = None

    employment_type: str | None = None

    salary_text: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_period: str | None = None

    published_at: datetime | None = None
    source_updated_at: datetime | None = None

    fetched_at: datetime


class CanonicalJob(BaseModel):
    """Logical real-world vacancy that may have multiple source postings."""

    canonical_key: str = Field(min_length=1)

    title: str = Field(min_length=1)
    company_name: str | None = None
    description_text: str | None = None

    location_text: str | None = None
    is_remote: bool | None = None
    remote_scope: str | None = None

    employment_type: str | None = None

    salary_text: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    salary_period: str | None = None

    published_at: datetime | None = None

    first_seen_at: datetime
    last_seen_at: datetime

    source_count: int = Field(default=1, ge=1)