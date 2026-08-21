"""Storage-independent read-only analytics query contract."""

from typing import Protocol

from job_market_analyzer.analytics.models import (
    AnalyticsOverview,
    PagedPostings,
    PostingSearchFilters,
    RoleDetail,
    SkillDetail,
    SourceSummary,
)


class AnalyticsRepository(Protocol):
    """Dashboard-oriented, posting-level, read-only query boundary."""

    def get_overview(self, *, top_limit: int = 10) -> AnalyticsOverview:
        """Return current posting, source, role, and skill aggregates."""

        ...

    def list_postings(
        self,
        filters: PostingSearchFilters = PostingSearchFilters(),
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> PagedPostings:
        """Return a stable page of current source postings."""

        ...

    def get_role_detail(
        self,
        role_code: str,
        *,
        top_limit: int = 10,
        posting_limit: int = 5,
    ) -> RoleDetail | None:
        """Return current posting and skill aggregates for an active role."""

        ...

    def get_skill_detail(
        self,
        skill_code: str,
        *,
        top_limit: int = 10,
        posting_limit: int = 5,
    ) -> SkillDetail | None:
        """Return current role and co-skill aggregates for an active skill."""

        ...

    def list_source_summaries(self) -> tuple[SourceSummary, ...]:
        """Return deterministic observed-data summaries by source provider."""

        ...
