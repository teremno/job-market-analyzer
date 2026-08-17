from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class RemoteScope(StrEnum):
    """How the remote-work geography is restricted."""

    WORLDWIDE = "worldwide"
    REGION = "region"
    COUNTRY = "country"
    TIMEZONE = "timezone"
    UNSPECIFIED = "unspecified"


class EmploymentType(StrEnum):
    """Normalized employment type when it can be determined reliably."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    OTHER = "other"


class SalaryPeriod(StrEnum):
    """Period represented by a salary value."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    PROJECT = "project"


class RawJob(BaseModel):
    """
    Immutable observation collected from an external source.

    `payload` contains the original source data.
    Other fields are collector metadata used for identity, routing,
    and provenance.
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(default_factory=uuid4)

    source_provider: str = Field(min_length=1)
    source_scope: str = Field(min_length=1)
    external_id: str = Field(min_length=1)

    source_url: HttpUrl
    fetched_at: AwareDatetime

    payload: dict[str, Any]

    @field_validator(
        "source_provider",
        "source_scope",
        "external_id",
    )
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value


class JobPosting(BaseModel):
    """
    Durable normalized vacancy posting on one specific source.

    Multiple RawJob observations may describe the same JobPosting
    at different points in time.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID = Field(default_factory=uuid4)

    canonical_job_id: UUID

    source_provider: str = Field(min_length=1)
    source_scope: str = Field(min_length=1)
    external_id: str = Field(min_length=1)

    source_url: HttpUrl
    application_url: HttpUrl | None = None

    title: str = Field(min_length=1)
    company_name: str | None = None
    description_text: str | None = None

    location_text: str | None = None
    is_remote: bool | None = None
    remote_scope: RemoteScope | None = None

    employment_type: EmploymentType | None = None

    salary_text: str | None = None
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None

    published_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None

    first_seen_at: AwareDatetime
    last_seen_at: AwareDatetime

    content_hash: str = Field(min_length=1)

    latest_raw_job_id: UUID | None = None

    @field_validator(
        "source_provider",
        "source_scope",
        "external_id",
        "title",
        "content_hash",
    )
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @field_validator("salary_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip().upper()

        if len(value) != 3 or not value.isalpha():
            raise ValueError(
                "salary_currency must be a 3-letter currency code"
            )

        return value

    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobPosting":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError(
                "salary_min must be less than or equal to salary_max"
            )

        return self

    @model_validator(mode="after")
    def validate_seen_range(self) -> "JobPosting":
        if self.first_seen_at > self.last_seen_at:
            raise ValueError(
                "first_seen_at must be less than or equal to last_seen_at"
            )

        return self


class CanonicalJob(BaseModel):
    """
    Logical real-world vacancy.

    Multiple source-specific JobPosting records may be linked to the
    same CanonicalJob.

    CanonicalJob intentionally does not duplicate salary, description,
    location, publication date, or other source-level data.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID = Field(default_factory=uuid4)

    created_at: AwareDatetime
    updated_at: AwareDatetime

    primary_posting_id: UUID | None = None

    @model_validator(mode="after")
    def validate_timestamp_range(self) -> "CanonicalJob":
        if self.created_at > self.updated_at:
            raise ValueError(
                "created_at must be less than or equal to updated_at"
            )

        return self