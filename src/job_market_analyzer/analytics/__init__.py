"""Stable public contracts for read-only Dashboard v0 analytics."""

from job_market_analyzer.analytics.models import (
    AnalysisStatus,
    AnalyticsOverview,
    NamedRole,
    NamedSkill,
    PagedPostings,
    PostingListItem,
    PostingSearchFilters,
    RoleCount,
    RoleDetail,
    SkillCount,
    SkillDetail,
    SourcePostingCount,
    SourceSummary,
)
from job_market_analyzer.analytics.repository import AnalyticsRepository
from job_market_analyzer.analytics.sqlite_repository import SQLiteAnalyticsRepository

__all__ = [
    "AnalysisStatus",
    "AnalyticsOverview",
    "AnalyticsRepository",
    "NamedRole",
    "NamedSkill",
    "PagedPostings",
    "PostingListItem",
    "PostingSearchFilters",
    "RoleCount",
    "RoleDetail",
    "SkillCount",
    "SkillDetail",
    "SQLiteAnalyticsRepository",
    "SourcePostingCount",
    "SourceSummary",
]
