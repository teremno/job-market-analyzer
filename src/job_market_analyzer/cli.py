"""Minimal console commands for controlled MVP operations."""

import argparse
import asyncio
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from job_market_analyzer.collectors.base import CollectionFailure
from job_market_analyzer.collectors.remote_ok import (
    REMOTE_OK_SOURCE_PROVIDER,
    REMOTE_OK_SOURCE_SCOPE,
    RemoteOKCollector,
)
from job_market_analyzer.normalization.remote_ok import normalize_remote_ok_job
from job_market_analyzer.services.collection import (
    CollectionSummary,
    collect_and_persist_jobs,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

DatabaseTotals = tuple[int, int, int]
VacancySample = tuple[str, str | None, str | None, str]


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and return a process exit code."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "collect-remote-ok":
        return collect_remote_ok(arguments.database)

    parser.error(f"Unsupported command: {arguments.command}")


def collect_remote_ok(database_path: Path) -> int:
    """Run one Remote OK collection against an explicitly selected SQLite file."""

    try:
        with closing(connect_database(database_path)) as connection:
            initialize_database(connection)
            repository = SQLiteJobRepository(connection)
            summary = asyncio.run(
                collect_and_persist_jobs(
                    RemoteOKCollector(),
                    normalize_remote_ok_job,
                    repository,
                )
            )
            totals, samples = _read_database_report(connection)
    except Exception as exc:
        print(
            f"Remote OK collection failed: {type(exc).__name__}: {_short_message(exc)}",
            file=sys.stderr,
        )
        return 1

    _print_summary(summary, totals, samples)
    if summary.failed:
        _print_failures(summary.failures)
        return 1

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-market-analyzer",
        description="Manual commands for the Job Market Analyzer MVP.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect_parser = subparsers.add_parser(
        "collect-remote-ok",
        help="Run one real Remote OK collection into SQLite.",
    )
    collect_parser.add_argument(
        "--database",
        required=True,
        type=Path,
        metavar="PATH",
        help="SQLite database path to create or reuse.",
    )
    return parser


def _read_database_report(
    connection: sqlite3.Connection,
) -> tuple[DatabaseTotals, list[VacancySample]]:
    totals_row = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM canonical_jobs) AS canonical_jobs,
            (SELECT COUNT(*) FROM job_postings) AS job_postings,
            (SELECT COUNT(*) FROM raw_jobs) AS raw_observations
        """
    ).fetchone()
    samples = connection.execute(
        """
        SELECT title, company_name, location_text, source_url
        FROM job_postings
        WHERE source_provider = ? AND source_scope = ?
        ORDER BY last_seen_at DESC, title COLLATE NOCASE, id
        LIMIT 5
        """,
        (REMOTE_OK_SOURCE_PROVIDER, REMOTE_OK_SOURCE_SCOPE),
    ).fetchall()

    totals: DatabaseTotals = (
        totals_row["canonical_jobs"],
        totals_row["job_postings"],
        totals_row["raw_observations"],
    )
    vacancy_samples = [
        (
            row["title"],
            row["company_name"],
            row["location_text"],
            row["source_url"],
        )
        for row in samples
    ]
    return totals, vacancy_samples


def _print_summary(
    summary: CollectionSummary,
    totals: DatabaseTotals,
    samples: list[VacancySample],
) -> None:
    print("Remote OK collection completed")
    print()
    print(f"Fetched: {summary.fetched}")
    print(f"Persisted: {summary.persisted}")
    print(f"Postings created: {summary.postings_created}")
    print(f"Raw observations created: {summary.raw_observations_created}")
    print(f"Failed: {summary.failed}")
    print()
    print(f"Canonical jobs: {totals[0]}")
    print(f"Job postings: {totals[1]}")
    print(f"Raw observations: {totals[2]}")
    print()
    print("Sample vacancies:")

    if not samples:
        print("- none")
        return

    for title, company, location, source_url in samples:
        print(f"- {title}")
        print(f"  Company: {company or 'n/a'}")
        print(f"  Location: {location or 'n/a'}")
        print(f"  Source URL: {source_url}")


def _print_failures(failures: tuple[CollectionFailure, ...]) -> None:
    print()
    print("Failures:")
    for failure in failures[:5]:
        identity = failure.external_id
        if identity is None:
            identity = (
                f"item {failure.item_index}"
                if failure.item_index is not None
                else "unknown item"
            )
        print(
            f"- {failure.stage} ({identity}): {_short_message(failure.message)}"
        )

    omitted = len(failures) - 5
    if omitted > 0:
        print(f"- {omitted} additional failure(s) not shown")


def _short_message(value: object, *, limit: int = 500) -> str:
    message = " ".join(str(value).split()) or "no details"
    if len(message) <= limit:
        return message
    return f"{message[: limit - 3]}..."
