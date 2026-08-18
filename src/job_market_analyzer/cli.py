"""Minimal console commands for controlled MVP operations."""

import argparse
import asyncio
import os
import sqlite3
import sys
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path

from job_market_analyzer.collectors.base import CollectionFailure, JobCollector
from job_market_analyzer.collectors.remote_ok import (
    REMOTE_OK_SOURCE_PROVIDER,
    REMOTE_OK_SOURCE_SCOPE,
    RemoteOKCollector,
)
from job_market_analyzer.collectors.web3_career import (
    WEB3_CAREER_SOURCE_PROVIDER,
    WEB3_CAREER_SOURCE_SCOPE,
    WEB3_CAREER_TOKEN_ENV,
    Web3CareerCollector,
)
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.normalization.remote_ok import normalize_remote_ok_job
from job_market_analyzer.normalization.web3_career import normalize_web3_career_job
from job_market_analyzer.services.collection import (
    CollectionSummary,
    collect_and_persist_jobs,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

DatabaseTotals = tuple[int, int, int]
VacancySample = tuple[str, str | None, str | None, str | None, str | None]
CollectorFactory = Callable[[], JobCollector]
JobNormalizer = Callable[[RawJob], NormalizedJobPosting]


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and return a process exit code."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "collect-remote-ok":
        return collect_remote_ok(arguments.database)
    if arguments.command == "collect-web3-career":
        return collect_web3_career(arguments.database)

    parser.error(f"Unsupported command: {arguments.command}")


def collect_remote_ok(database_path: Path) -> int:
    """Run one Remote OK collection against an explicitly selected SQLite file."""

    return _collect_once(
        database_path,
        source_name="Remote OK",
        source_provider=REMOTE_OK_SOURCE_PROVIDER,
        source_scope=REMOTE_OK_SOURCE_SCOPE,
        collector_factory=RemoteOKCollector,
        normalizer=normalize_remote_ok_job,
    )


def collect_web3_career(database_path: Path) -> int:
    """Run one Web3.career collection using its environment-provided API token."""

    return _collect_once(
        database_path,
        source_name="Web3.career",
        source_provider=WEB3_CAREER_SOURCE_PROVIDER,
        source_scope=WEB3_CAREER_SOURCE_SCOPE,
        collector_factory=Web3CareerCollector,
        normalizer=normalize_web3_career_job,
        secret_env_name=WEB3_CAREER_TOKEN_ENV,
    )


def _collect_once(
    database_path: Path,
    *,
    source_name: str,
    source_provider: str,
    source_scope: str,
    collector_factory: CollectorFactory,
    normalizer: JobNormalizer,
    secret_env_name: str | None = None,
) -> int:
    """Run one source collection and print a source-filtered SQLite report."""

    sensitive_values = _environment_secret_values(secret_env_name)
    try:
        collector = collector_factory()
        with closing(connect_database(database_path)) as connection:
            initialize_database(connection)
            repository = SQLiteJobRepository(connection)
            summary = asyncio.run(
                collect_and_persist_jobs(
                    collector,
                    normalizer,
                    repository,
                )
            )
            totals, samples = _read_database_report(
                connection,
                source_provider=source_provider,
                source_scope=source_scope,
            )
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts failures to exit 1
        print(
            f"{source_name} collection failed: {type(exc).__name__}: "
            f"{_short_message(exc, sensitive_values=sensitive_values)}",
            file=sys.stderr,
        )
        return 1

    _print_summary(
        source_name,
        summary,
        totals,
        samples,
        sensitive_values=sensitive_values,
    )
    if summary.failed:
        _print_failures(summary.failures, sensitive_values=sensitive_values)
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
    web3_collect_parser = subparsers.add_parser(
        "collect-web3-career",
        help="Run one real Web3.career collection into SQLite.",
    )
    web3_collect_parser.add_argument(
        "--database",
        required=True,
        type=Path,
        metavar="PATH",
        help="SQLite database path to create or reuse.",
    )
    return parser


def _read_database_report(
    connection: sqlite3.Connection,
    *,
    source_provider: str,
    source_scope: str,
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
        SELECT title, company_name, location_text, source_url, application_url
        FROM job_postings
        WHERE source_provider = ? AND source_scope = ?
        ORDER BY last_seen_at DESC, title COLLATE NOCASE, id
        LIMIT 5
        """,
        (source_provider, source_scope),
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
            row["application_url"],
        )
        for row in samples
    ]
    return totals, vacancy_samples


def _print_summary(
    source_name: str,
    summary: CollectionSummary,
    totals: DatabaseTotals,
    samples: list[VacancySample],
    *,
    sensitive_values: Sequence[str] = (),
) -> None:
    print(f"{source_name} collection completed")
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

    for title, company, location, source_url, application_url in samples:
        print(f"- {_redact_sensitive(title, sensitive_values)}")
        print(
            f"  Company: "
            f"{_redact_sensitive(company or 'n/a', sensitive_values)}"
        )
        print(
            f"  Location: "
            f"{_redact_sensitive(location or 'n/a', sensitive_values)}"
        )
        print(
            f"  Source URL: "
            f"{_redact_sensitive(source_url or 'n/a', sensitive_values)}"
        )
        if application_url is not None:
            print(
                "  Application URL: "
                f"{_redact_sensitive(application_url, sensitive_values)}"
            )


def _print_failures(
    failures: tuple[CollectionFailure, ...],
    *,
    sensitive_values: Sequence[str] = (),
) -> None:
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
        identity = _redact_sensitive(identity, sensitive_values)
        print(
            f"- {failure.stage} ({identity}): "
            f"{_short_message(failure.message, sensitive_values=sensitive_values)}"
        )

    omitted = len(failures) - 5
    if omitted > 0:
        print(f"- {omitted} additional failure(s) not shown")


def _environment_secret_values(secret_env_name: str | None) -> tuple[str, ...]:
    if secret_env_name is None:
        return ()

    secret = os.getenv(secret_env_name)
    if secret is None or not secret:
        return ()
    return (secret,)


def _short_message(
    value: object,
    *,
    limit: int = 500,
    sensitive_values: Sequence[str] = (),
) -> str:
    message = " ".join(str(value).split()) or "no details"
    message = _redact_sensitive(message, sensitive_values)
    if len(message) <= limit:
        return message
    return f"{message[: limit - 3]}..."


def _redact_sensitive(value: str, sensitive_values: Sequence[str]) -> str:
    message = value
    for sensitive_value in sensitive_values:
        message = message.replace(sensitive_value, "[REDACTED]")
    return message
