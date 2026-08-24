"""Explicit source and language-aware analyzer registrations for guided update."""

import sqlite3

from job_market_analyzer.collectors.ashby import (
    ASHBY_SOURCE_PROVIDER,
    AshbyCollector,
)
from job_market_analyzer.collectors.the_muse import (
    THE_MUSE_SOURCE_PROVIDER,
    TheMuseCollector,
)
from job_market_analyzer.collectors.greenhouse import (
    GREENHOUSE_SOURCE_PROVIDER,
    GreenhouseCollector,
)
from job_market_analyzer.collectors.himalayas import (
    HIMALAYAS_SOURCE_PROVIDER,
    HimalayasCollector,
)
from job_market_analyzer.collectors.jobicy import (
    JOBICY_SOURCE_PROVIDER,
    JobicyCollector,
)
from job_market_analyzer.collectors.lever import (
    LEVER_SOURCE_PROVIDER,
    LeverCollector,
)
from job_market_analyzer.collectors.remote_ok import (
    REMOTE_OK_SOURCE_PROVIDER,
    RemoteOKCollector,
)
from job_market_analyzer.collectors.remotive import (
    REMOTIVE_SOURCE_PROVIDER,
    RemotiveCollector,
)
from job_market_analyzer.collectors.web3_career import (
    WEB3_CAREER_SOURCE_PROVIDER,
    WEB3_CAREER_TOKEN_ENV,
    Web3CareerCollector,
)
from job_market_analyzer.collectors.we_work_remotely import (
    WE_WORK_REMOTELY_SOURCE_PROVIDER,
    WeWorkRemotelyCollector,
)
from job_market_analyzer.intelligence.geography import GEOGRAPHY_TAXONOMY_VERSION
from job_market_analyzer.intelligence.roles import ROLE_TAXONOMY_VERSION
from job_market_analyzer.intelligence.salaries import SALARY_TAXONOMY_VERSION
from job_market_analyzer.intelligence.seniority import SENIORITY_TAXONOMY_VERSION
from job_market_analyzer.intelligence.skills import SKILL_TAXONOMY_VERSION
from job_market_analyzer.normalization.ashby import normalize_ashby_job
from job_market_analyzer.normalization.the_muse import normalize_the_muse_job
from job_market_analyzer.normalization.greenhouse import normalize_greenhouse_job
from job_market_analyzer.normalization.himalayas import normalize_himalayas_job
from job_market_analyzer.normalization.jobicy import normalize_jobicy_job
from job_market_analyzer.normalization.lever import normalize_lever_job
from job_market_analyzer.normalization.remote_ok import normalize_remote_ok_job
from job_market_analyzer.normalization.remotive import normalize_remotive_job
from job_market_analyzer.normalization.web3_career import normalize_web3_career_job
from job_market_analyzer.normalization.we_work_remotely import (
    normalize_we_work_remotely_job,
)
from job_market_analyzer.services.geography_smoke import run_geography_smoke
from job_market_analyzer.services.role_smoke import run_role_smoke
from job_market_analyzer.services.salary_smoke import run_salary_smoke
from job_market_analyzer.services.seniority_smoke import run_seniority_smoke
from job_market_analyzer.services.skill_smoke import run_skill_smoke
from job_market_analyzer.services.update import (
    AnalyzerAdapter,
    AnalyzerExecutionSummary,
    SourceAdapter,
)
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteGeographyIntelligenceRepository,
    SQLiteRoleIntelligenceRepository,
    SQLiteSalaryIntelligenceRepository,
    SQLiteSeniorityIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

ANALYSIS_LANGUAGE_CHOICES = ("en", "uk")

SOURCE_REGISTRY: tuple[SourceAdapter, ...] = (
    SourceAdapter(
        REMOTE_OK_SOURCE_PROVIDER,
        "Remote OK",
        RemoteOKCollector,
        normalize_remote_ok_job,
    ),
    SourceAdapter(
        WEB3_CAREER_SOURCE_PROVIDER,
        "Web3.career",
        Web3CareerCollector,
        normalize_web3_career_job,
        credential_env=WEB3_CAREER_TOKEN_ENV,
    ),
    SourceAdapter(
        HIMALAYAS_SOURCE_PROVIDER,
        "Himalayas",
        HimalayasCollector,
        normalize_himalayas_job,
    ),
    SourceAdapter(
        JOBICY_SOURCE_PROVIDER,
        "Jobicy",
        JobicyCollector,
        normalize_jobicy_job,
    ),
    SourceAdapter(
        REMOTIVE_SOURCE_PROVIDER,
        "Remotive",
        RemotiveCollector,
        normalize_remotive_job,
    ),
    SourceAdapter(
        WE_WORK_REMOTELY_SOURCE_PROVIDER,
        "We Work Remotely",
        WeWorkRemotelyCollector,
        normalize_we_work_remotely_job,
    ),
    SourceAdapter(
        GREENHOUSE_SOURCE_PROVIDER,
        "Greenhouse",
        GreenhouseCollector,
        normalize_greenhouse_job,
    ),
    SourceAdapter(
        LEVER_SOURCE_PROVIDER,
        "Lever",
        LeverCollector,
        normalize_lever_job,
    ),
    SourceAdapter(
        ASHBY_SOURCE_PROVIDER,
        "Ashby",
        AshbyCollector,
        normalize_ashby_job,
    ),
    SourceAdapter(
        THE_MUSE_SOURCE_PROVIDER,
        "The Muse",
        TheMuseCollector,
        normalize_the_muse_job,
    ),
)


def _run_skills(
    connection: sqlite3.Connection,
    limit: int,
) -> AnalyzerExecutionSummary:
    summary = run_skill_smoke(
        SQLiteJobRepository(connection),
        SQLiteSkillIntelligenceRepository(connection),
        limit=limit,
        sample_limit=0,
    )
    return AnalyzerExecutionSummary(
        postings_considered=summary.postings_considered,
        runs_created=summary.new_analysis_runs,
        runs_reused=summary.existing_analysis_runs_reused,
    )


def _run_roles(
    connection: sqlite3.Connection,
    limit: int,
) -> AnalyzerExecutionSummary:
    summary = run_role_smoke(
        SQLiteJobRepository(connection),
        SQLiteRoleIntelligenceRepository(connection),
        limit=limit,
        sample_limit=0,
    )
    return AnalyzerExecutionSummary(
        postings_considered=summary.postings_considered,
        runs_created=summary.new_analysis_runs,
        runs_reused=summary.existing_analysis_runs_reused,
    )


def _run_seniority(
    connection: sqlite3.Connection,
    limit: int,
) -> AnalyzerExecutionSummary:
    summary = run_seniority_smoke(
        SQLiteJobRepository(connection),
        SQLiteSeniorityIntelligenceRepository(connection),
        limit=limit,
        sample_limit=0,
    )
    return AnalyzerExecutionSummary(
        postings_considered=summary.postings_considered,
        runs_created=summary.new_analysis_runs,
        runs_reused=summary.existing_analysis_runs_reused,
    )


def _run_geography(
    connection: sqlite3.Connection,
    limit: int,
) -> AnalyzerExecutionSummary:
    summary = run_geography_smoke(
        SQLiteJobRepository(connection),
        SQLiteGeographyIntelligenceRepository(connection),
        limit=limit,
        sample_limit=0,
    )
    return AnalyzerExecutionSummary(
        postings_considered=summary.postings_considered,
        runs_created=summary.new_analysis_runs,
        runs_reused=summary.existing_analysis_runs_reused,
    )


def _run_salary(
    connection: sqlite3.Connection,
    limit: int,
) -> AnalyzerExecutionSummary:
    summary = run_salary_smoke(
        SQLiteJobRepository(connection),
        SQLiteSalaryIntelligenceRepository(connection),
        limit=limit,
    )
    return AnalyzerExecutionSummary(
        postings_considered=summary.postings_considered,
        runs_created=summary.new_analysis_runs,
        runs_reused=summary.existing_analysis_runs_reused,
    )


ANALYZER_REGISTRY: tuple[AnalyzerAdapter, ...] = (
    AnalyzerAdapter(
        kind="skills",
        display_name="Skills",
        language="en",
        version=SKILL_TAXONOMY_VERSION,
        runner=_run_skills,
    ),
    AnalyzerAdapter(
        kind="roles",
        display_name="Roles",
        language="en",
        version=ROLE_TAXONOMY_VERSION,
        runner=_run_roles,
    ),
    AnalyzerAdapter(
        kind="seniority",
        display_name="Seniority",
        language="en",
        version=SENIORITY_TAXONOMY_VERSION,
        runner=_run_seniority,
    ),
    AnalyzerAdapter(
        kind="geography",
        display_name="Geography",
        language="en",
        version=GEOGRAPHY_TAXONOMY_VERSION,
        runner=_run_geography,
    ),
    AnalyzerAdapter(
        kind="salary",
        display_name="Salary",
        language="en",
        version=SALARY_TAXONOMY_VERSION,
        runner=_run_salary,
    ),
)
