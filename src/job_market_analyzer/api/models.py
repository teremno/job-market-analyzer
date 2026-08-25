"""Explicit, frontend-friendly response models for the local API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from job_market_analyzer.analytics import (
    AnalyticsOverview,
    PagedPostings,
    PostingListItem,
    RoleCount,
    RoleDetail,
    SalaryCurrencySummary,
    SkillCount,
    SkillDetail,
    SourcePostingCount,
    SourceSummary,
    TermCount,
)


class ApiModel(BaseModel):
    """Reject accidental undeclared response fields."""

    model_config = ConfigDict(extra="forbid")


class ErrorDetail(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorDetail
    request_id: UUID


class HealthResponse(ApiModel):
    status: str
    schema_version: int


class AnalysisStatusCounts(ApiModel):
    not_analyzed: int
    analyzed_zero: int
    analyzed_with_results: int


class AnalysisCoverage(AnalysisStatusCounts):
    with_results_percentage: float


class RoleCountResponse(ApiModel):
    role_code: str
    role_name: str
    posting_count: int

    @classmethod
    def from_dto(cls, value: RoleCount) -> "RoleCountResponse":
        return cls(
            role_code=value.role_code,
            role_name=value.role_name,
            posting_count=value.posting_count,
        )


class SkillCountResponse(ApiModel):
    skill_code: str
    skill_name: str
    posting_count: int

    @classmethod
    def from_dto(cls, value: SkillCount) -> "SkillCountResponse":
        return cls(
            skill_code=value.skill_code,
            skill_name=value.skill_name,
            posting_count=value.posting_count,
        )


class SourcePostingCountResponse(ApiModel):
    source_provider: str
    posting_count: int

    @classmethod
    def from_dto(cls, value: SourcePostingCount) -> "SourcePostingCountResponse":
        return cls(
            source_provider=value.source_provider,
            posting_count=value.posting_count,
        )


class TermCountResponse(ApiModel):
    term_code: str
    term_name: str
    posting_count: int

    @classmethod
    def from_dto(cls, value: TermCount) -> "TermCountResponse":
        return cls(
            term_code=value.term_code,
            term_name=value.term_name,
            posting_count=value.posting_count,
        )


class SalaryCurrencySummaryResponse(ApiModel):
    currency: str
    postings: int
    median_annual_min: str | None

    @classmethod
    def from_dto(cls, value: SalaryCurrencySummary) -> "SalaryCurrencySummaryResponse":
        return cls(
            currency=value.currency,
            postings=value.postings,
            median_annual_min=value.median_annual_min,
        )


class NamedTermResponse(ApiModel):
    code: str
    name: str


class MarketSkillResponse(ApiModel):
    skill_code: str
    skill_name: str
    posting_count: int
    share_of_role_postings: float
    status: str


class SkillGapResponse(ApiModel):
    role_code: str
    role_name: str
    role_posting_count: int
    known_recognized: tuple[str, ...]
    unknown_inputs: tuple[str, ...]
    gaps: tuple[MarketSkillResponse, ...]
    matched_market_skills: tuple[MarketSkillResponse, ...]


class AnalyticsOverviewResponse(ApiModel):
    posting_count: int
    source_count: int
    role_analysis: AnalysisStatusCounts
    skill_analysis: AnalysisStatusCounts
    postings_by_source: tuple[SourcePostingCountResponse, ...]
    top_roles: tuple[RoleCountResponse, ...]
    top_skills: tuple[SkillCountResponse, ...]
    top_seniority: tuple[TermCountResponse, ...]
    arrangement_counts: tuple[TermCountResponse, ...]
    region_counts: tuple[TermCountResponse, ...]
    salary_posting_count: int
    salary_currencies: tuple[SalaryCurrencySummaryResponse, ...]

    @classmethod
    def from_dto(cls, value: AnalyticsOverview) -> "AnalyticsOverviewResponse":
        return cls(
            posting_count=value.posting_count,
            source_count=value.source_count,
            role_analysis=AnalysisStatusCounts(
                not_analyzed=value.current_role_not_analyzed_posting_count,
                analyzed_zero=value.current_role_unknown_posting_count,
                analyzed_with_results=value.current_role_classified_posting_count,
            ),
            skill_analysis=AnalysisStatusCounts(
                not_analyzed=value.current_skill_not_analyzed_posting_count,
                analyzed_zero=value.current_skill_zero_posting_count,
                analyzed_with_results=value.current_skill_classified_posting_count,
            ),
            postings_by_source=tuple(
                SourcePostingCountResponse.from_dto(item)
                for item in value.postings_by_source
            ),
            top_roles=tuple(RoleCountResponse.from_dto(item) for item in value.top_roles),
            top_skills=tuple(
                SkillCountResponse.from_dto(item) for item in value.top_skills
            ),
            top_seniority=tuple(
                TermCountResponse.from_dto(item) for item in value.top_seniority
            ),
            arrangement_counts=tuple(
                TermCountResponse.from_dto(item) for item in value.arrangement_counts
            ),
            region_counts=tuple(
                TermCountResponse.from_dto(item) for item in value.region_counts
            ),
            salary_posting_count=value.salary_posting_count,
            salary_currencies=tuple(
                SalaryCurrencySummaryResponse.from_dto(item)
                for item in value.salary_currencies
            ),
        )


class NamedRoleResponse(ApiModel):
    role_code: str
    role_name: str


class NamedSkillResponse(ApiModel):
    skill_code: str
    skill_name: str


class PostingResponse(ApiModel):
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
    role_analysis_status: str
    skill_analysis_status: str
    roles: tuple[NamedRoleResponse, ...]
    skills: tuple[NamedSkillResponse, ...]
    seniority: NamedTermResponse | None = None
    arrangement: NamedTermResponse | None = None
    regions: tuple[NamedTermResponse, ...] = ()
    salary_currency: str | None = None
    salary_annual_min: str | None = None
    salary_annual_max: str | None = None

    @classmethod
    def from_dto(cls, value: PostingListItem) -> "PostingResponse":
        return cls(
            job_posting_id=value.job_posting_id,
            canonical_job_id=value.canonical_job_id,
            source_provider=value.source_provider,
            source_scope=value.source_scope,
            external_id=value.external_id,
            company_name=value.company_name,
            title=value.title,
            location=value.location,
            published_at=value.published_at,
            source_url=value.source_url,
            application_url=value.application_url,
            role_analysis_status=value.role_analysis_status.value,
            skill_analysis_status=value.skill_analysis_status.value,
            roles=tuple(
                NamedRoleResponse(role_code=item.role_code, role_name=item.role_name)
                for item in value.roles
            ),
            skills=tuple(
                NamedSkillResponse(skill_code=item.skill_code, skill_name=item.skill_name)
                for item in value.skills
            ),
            seniority=None
            if value.seniority is None
            else NamedTermResponse(code=value.seniority.code, name=value.seniority.name),
            arrangement=None
            if value.arrangement is None
            else NamedTermResponse(
                code=value.arrangement.code, name=value.arrangement.name
            ),
            regions=tuple(
                NamedTermResponse(code=item.code, name=item.name)
                for item in value.regions
            ),
            salary_currency=value.salary_currency,
            salary_annual_min=value.salary_annual_min,
            salary_annual_max=value.salary_annual_max,
        )


class JobsResponse(ApiModel):
    items: tuple[PostingResponse, ...]
    limit: int
    offset: int
    total: int

    @classmethod
    def from_dto(cls, value: PagedPostings) -> "JobsResponse":
        return cls(
            items=tuple(PostingResponse.from_dto(item) for item in value.items),
            limit=value.limit,
            offset=value.offset,
            total=value.posting_count,
        )


class RoleDetailResponse(ApiModel):
    role_code: str
    role_name: str
    posting_count: int
    top_skills: tuple[SkillCountResponse, ...]
    representative_postings: tuple[PostingResponse, ...]

    @classmethod
    def from_dto(cls, value: RoleDetail) -> "RoleDetailResponse":
        return cls(
            role_code=value.role_code,
            role_name=value.role_name,
            posting_count=value.posting_count,
            top_skills=tuple(
                SkillCountResponse.from_dto(item) for item in value.top_skills
            ),
            representative_postings=tuple(
                PostingResponse.from_dto(item) for item in value.representative_postings
            ),
        )


class SkillDetailResponse(ApiModel):
    skill_code: str
    skill_name: str
    posting_count: int
    associated_roles: tuple[RoleCountResponse, ...]
    co_occurring_skills: tuple[SkillCountResponse, ...]
    representative_postings: tuple[PostingResponse, ...]

    @classmethod
    def from_dto(cls, value: SkillDetail) -> "SkillDetailResponse":
        return cls(
            skill_code=value.skill_code,
            skill_name=value.skill_name,
            posting_count=value.posting_count,
            associated_roles=tuple(
                RoleCountResponse.from_dto(item) for item in value.top_roles
            ),
            co_occurring_skills=tuple(
                SkillCountResponse.from_dto(item) for item in value.co_occurring_skills
            ),
            representative_postings=tuple(
                PostingResponse.from_dto(item) for item in value.representative_postings
            ),
        )


class SourceSummaryResponse(ApiModel):
    source_provider: str
    posting_count: int
    newest_published_at: datetime | None
    newest_last_seen_at: datetime
    role_analysis: AnalysisCoverage
    skill_analysis: AnalysisCoverage
    last_update_status: str | None = None
    last_update_finished_at: datetime | None = None
    last_successful_update_at: datetime | None = None

    @classmethod
    def from_dto(cls, value: SourceSummary) -> "SourceSummaryResponse":
        return cls(
            source_provider=value.source_provider,
            posting_count=value.posting_count,
            newest_published_at=value.newest_published_at,
            newest_last_seen_at=value.newest_last_seen_at,
            role_analysis=AnalysisCoverage(
                not_analyzed=value.current_role_not_analyzed_posting_count,
                analyzed_zero=value.current_role_unknown_posting_count,
                analyzed_with_results=value.current_role_classified_posting_count,
                with_results_percentage=value.current_role_classified_percentage,
            ),
            skill_analysis=AnalysisCoverage(
                not_analyzed=value.current_skill_not_analyzed_posting_count,
                analyzed_zero=value.current_skill_zero_posting_count,
                analyzed_with_results=value.current_skill_classified_posting_count,
                with_results_percentage=value.current_skill_classified_percentage,
            ),
            last_update_status=value.last_update_status,
            last_update_finished_at=value.last_update_finished_at,
            last_successful_update_at=value.last_successful_update_at,
        )
