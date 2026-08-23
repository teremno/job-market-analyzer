"""Stable public contracts for read-only Dashboard v0 analytics."""

from job_market_analyzer.analytics.models import (
    AnalysisStatus,
    AnalyticsOverview,
    NamedRole,
    NamedSkill,
    NamedTerm,
    PagedPostings,
    PostingListItem,
    PostingSearchFilters,
    RoleCount,
    RoleDetail,
    SalaryCurrencySummary,
    SkillCount,
    SkillDetail,
    SourcePostingCount,
    SourceSummary,
    TermCount,
)
from job_market_analyzer.analytics.repository import AnalyticsRepository
from job_market_analyzer.analytics.sqlite_repository import SQLiteAnalyticsRepository

__all__ = [
    "AnalysisStatus",
    "AnalyticsOverview",
    "AnalyticsRepository",
    "NamedRole",
    "NamedSkill",
    "NamedTerm",
    "PagedPostings",
    "PostingListItem",
    "PostingSearchFilters",
    "RoleCount",
    "RoleDetail",
    "SalaryCurrencySummary",
    "SkillCount",
    "SkillDetail",
    "SQLiteAnalyticsRepository",
    "SourcePostingCount",
    "SourceSummary",
    "TermCount",
]
