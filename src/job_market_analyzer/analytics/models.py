"""Immutable, UI-independent result models for posting-level analytics."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AnalysisStatus(StrEnum):
    """Compatibility state of one posting's active analyzer result."""

    NOT_ANALYZED = "not_analyzed"
    ANALYZED_ZERO = "analyzed_zero"
    ANALYZED_WITH_RESULTS = "analyzed_with_results"


@dataclass(frozen=True, slots=True)
class RoleCount:
    """Posting-level count for one stable role code."""

    role_code: str
    role_name: str
    posting_count: int


@dataclass(frozen=True, slots=True)
class SkillCount:
    """Posting-level count for one stable skill code."""

    skill_code: str
    skill_name: str
    posting_count: int


@dataclass(frozen=True, slots=True)
class TermCount:
    """Posting-level count for one seniority or geography term."""

    term_code: str
    term_name: str
    posting_count: int


@dataclass(frozen=True, slots=True)
class NamedTerm:
    """Stable seniority/geography identity with a display label."""

    code: str
    name: str


@dataclass(frozen=True, slots=True)
class SalaryCurrencySummary:
    """Posting-level salary coverage for one currency."""

    currency: str
    postings: int
    median_annual_min: str | None


@dataclass(frozen=True, slots=True)
class SourcePostingCount:
    """Current durable posting count for one source provider."""

    source_provider: str
    posting_count: int


@dataclass(frozen=True, slots=True)
class AnalyticsOverview:
    """Small posting-level overview required by Dashboard v0."""

    posting_count: int
    source_count: int
    current_role_classified_posting_count: int
    current_role_unknown_posting_count: int
    current_role_not_analyzed_posting_count: int
    current_skill_classified_posting_count: int
    current_skill_zero_posting_count: int
    current_skill_not_analyzed_posting_count: int
    postings_by_source: tuple[SourcePostingCount, ...]
    top_roles: tuple[RoleCount, ...]
    top_skills: tuple[SkillCount, ...]
    top_seniority: tuple[TermCount, ...]
    arrangement_counts: tuple[TermCount, ...]
    region_counts: tuple[TermCount, ...]
    salary_posting_count: int
    salary_currencies: tuple[SalaryCurrencySummary, ...]


@dataclass(frozen=True, slots=True)
class PostingSearchFilters:
    """Optional, machine-identity filters for the current posting list."""

    source_provider: str | None = None
    role_code: str | None = None
    skill_code: str | None = None
    seniority_code: str | None = None
    geography_code: str | None = None
    has_salary: bool | None = None
    search_text: str | None = None

    def __post_init__(self) -> None:
        """Normalize whitespace without translating identity values."""

        for field_name in (
            "source_provider",
            "role_code",
            "skill_code",
            "seniority_code",
            "geography_code",
            "search_text",
        ):
            value = getattr(self, field_name)
            if value is not None:
                normalized = value.strip()
                object.__setattr__(
                    self,
                    field_name,
                    normalized if normalized else None,
                )


@dataclass(frozen=True, slots=True)
class NamedRole:
    """Stable role identity with the current default display label."""

    role_code: str
    role_name: str


@dataclass(frozen=True, slots=True)
class NamedSkill:
    """Stable skill identity with the current default display label."""

    skill_code: str
    skill_name: str


@dataclass(frozen=True, slots=True)
class PostingListItem:
    """Bounded posting projection without description or raw payload."""

    job_posting_id: UUID
    canonical_job_id: UUID
    source_provider: str
    source_scope: str
    external_id: str
    company_name: str | None
    title: str
    location: str | None
    published_at: datetime | None
    source_url: str | None
    application_url: str | None
    role_analysis_status: AnalysisStatus
    skill_analysis_status: AnalysisStatus
    roles: tuple[NamedRole, ...]
    skills: tuple[NamedSkill, ...]
    seniority: NamedTerm | None = None
    arrangement: NamedTerm | None = None
    regions: tuple[NamedTerm, ...] = ()
    salary_currency: str | None = None
    salary_annual_min: str | None = None
    salary_annual_max: str | None = None


@dataclass(frozen=True, slots=True)
class PagedPostings:
    """Offset-paginated current posting results."""

    items: tuple[PostingListItem, ...]
    posting_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class RoleDetail:
    """Posting-level detail for one active role code."""

    role_code: str
    role_name: str
    posting_count: int
    top_skills: tuple[SkillCount, ...]
    representative_postings: tuple[PostingListItem, ...]


@dataclass(frozen=True, slots=True)
class SkillDetail:
    """Posting-level detail for one active skill code."""

    skill_code: str
    skill_name: str
    posting_count: int
    top_roles: tuple[RoleCount, ...]
    co_occurring_skills: tuple[SkillCount, ...]
    representative_postings: tuple[PostingListItem, ...]


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """Observed dataset summary for one provider, not collector uptime."""

    source_provider: str
    posting_count: int
    newest_published_at: datetime | None
    newest_last_seen_at: datetime
    current_role_classified_posting_count: int
    current_role_unknown_posting_count: int
    current_role_not_analyzed_posting_count: int
    current_role_classified_percentage: float
    current_skill_classified_posting_count: int
    current_skill_zero_posting_count: int
    current_skill_not_analyzed_posting_count: int
    current_skill_classified_percentage: float
