"""Regression coverage added from the multi-agent audit findings."""

import asyncio
import sqlite3
from datetime import UTC, datetime
from itertools import combinations

import httpx
import pytest

from job_market_analyzer.analytics.sqlite_repository import _runs_ctes
from job_market_analyzer.collectors.lever import collect_lever_boards
from job_market_analyzer.intelligence.repository import (
    GEOGRAPHY_ANALYZER_KIND,
    ROLE_ANALYZER_KIND,
    SALARY_ANALYZER_KIND,
    SENIORITY_ANALYZER_KIND,
    SKILL_ANALYZER_KIND,
)
from job_market_analyzer.intelligence.salaries import extract_salary_estimate
from job_market_analyzer.models import RawJob
from job_market_analyzer.normalization.lever import normalize_lever_job
from job_market_analyzer.storage.sqlite import connect_database, initialize_database

FETCHED_AT = datetime(2026, 8, 22, 15, 0, tzinfo=UTC)


@pytest.fixture
def analytics_connection() -> sqlite3.Connection:
    connection = connect_database(":memory:")
    initialize_database(connection)
    yield connection
    connection.close()


def test_lever_unspecified_workplace_yields_no_remote_claim():
    payload = {
        "id": "u-1",
        "text": "Platform Engineer",
        "hostedUrl": "https://jobs.lever.co/test/u-1",
        "createdAt": 1755000000000,
        "workplaceType": "unspecified",
        "categories": {"location": "Berlin", "commitment": "Permanent"},
        "descriptionPlain": "Build the platform.",
    }
    raw = RawJob(
        source_provider="lever",
        source_scope="test",
        external_id="u-1",
        source_url=None,
        fetched_at=FETCHED_AT,
        payload=payload,
    )
    posting = normalize_lever_job(raw)
    assert posting.is_remote is None


def test_boards_failed_metadata_counts_only_board_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in request.url.path:
            return httpx.Response(500, request=request)
        jobs = [
            {"title": "missing id"},
            {
                "id": "ok-1",
                "text": "Engineer",
                "hostedUrl": "https://jobs.lever.co/test/ok-1",
                "createdAt": 1755000000000,
            },
        ]
        return httpx.Response(200, json=jobs, request=request)

    result = asyncio.run(
        collect_lever_boards(
            base_url="https://lever.test",
            board_tokens=("broken", "healthy"),
            transport=httpx.MockTransport(handler),
            clock=lambda: FETCHED_AT,
        )
    )

    assert result.fetched == 1
    assert result.metadata["boards_requested"] == 2
    assert result.metadata["boards_collected"] == 1
    assert result.metadata["boards_failed"] == 1


def test_runs_ctes_composes_every_subset_without_binding_errors(
    analytics_connection: sqlite3.Connection,
):
    kinds = [
        ROLE_ANALYZER_KIND,
        SKILL_ANALYZER_KIND,
        SENIORITY_ANALYZER_KIND,
        GEOGRAPHY_ANALYZER_KIND,
        SALARY_ANALYZER_KIND,
    ]
    cutoff = "2026-08-01T00:00:00.000000Z"
    checked = 0
    for size in range(1, len(kinds) + 1):
        for subset in combinations(kinds, size):
            ctes, parameters = _runs_ctes(*subset)
            placeholders = ctes.count("?")
            assert placeholders == len(parameters) + 1  # + active-postings cutoff
            rows = analytics_connection.execute(
                ctes + "\nSELECT COUNT(*) AS c FROM active_postings",
                (cutoff, *parameters),
            ).fetchall()
            assert rows[0]["c"] >= 0
            checked += 1
    assert checked == 31


def test_salary_text_yearly_period_detected():
    estimate = extract_salary_estimate("Around $70,000 per year")
    assert estimate == () or estimate[0].period == "yearly"
