"""Minimal console commands for controlled MVP operations."""

import argparse
import asyncio
import ipaddress
import os
import sqlite3
import sys
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path

import uvicorn

from job_market_analyzer.collectors.base import CollectionFailure, JobCollector
from job_market_analyzer.api import create_app
from job_market_analyzer.api.dependencies import DatabaseConfigurationError
from job_market_analyzer.collectors.himalayas import (
    HIMALAYAS_SOURCE_PROVIDER,
    HIMALAYAS_SOURCE_SCOPE,
    HimalayasCollector,
)
from job_market_analyzer.collectors.jobicy import (
    JOBICY_SOURCE_PROVIDER,
    JOBICY_SOURCE_SCOPE,
    JobicyCollector,
)
from job_market_analyzer.collectors.remotive import (
    REMOTIVE_SOURCE_PROVIDER,
    REMOTIVE_SOURCE_SCOPE,
    RemotiveCollector,
)
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
from job_market_analyzer.collectors.we_work_remotely import (
    WE_WORK_REMOTELY_SOURCE_PROVIDER,
    WE_WORK_REMOTELY_SOURCE_SCOPE,
    WeWorkRemotelyCollector,
)
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.intelligence.skills import SKILL_TAXONOMY_VERSION
from job_market_analyzer.intelligence.roles import ROLE_TAXONOMY_VERSION
from job_market_analyzer.normalization.remote_ok import normalize_remote_ok_job
from job_market_analyzer.normalization.himalayas import normalize_himalayas_job
from job_market_analyzer.normalization.jobicy import normalize_jobicy_job
from job_market_analyzer.normalization.remotive import normalize_remotive_job
from job_market_analyzer.normalization.web3_career import normalize_web3_career_job
from job_market_analyzer.normalization.we_work_remotely import (
    normalize_we_work_remotely_job,
)
from job_market_analyzer.services.collection import (
    CollectionSummary,
    collect_and_persist_jobs,
)
from job_market_analyzer.services.skill_smoke import (
    SkillSmokeSummary,
    run_skill_smoke,
)
from job_market_analyzer.services.role_smoke import (
    RoleSmokeSummary,
    run_role_smoke,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteRoleIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

DatabaseTotals = tuple[int, int, int]
VacancySample = tuple[str, str | None, str | None, str | None, str | None]
CollectorFactory = Callable[[], JobCollector]
JobNormalizer = Callable[[RawJob], NormalizedJobPosting]


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and return a process exit code."""

    _configure_console_streams()
    parser = _build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "collect-remote-ok":
        return collect_remote_ok(arguments.database)
    if arguments.command == "collect-web3-career":
        return collect_web3_career(arguments.database)
    if arguments.command == "collect-himalayas":
        return collect_himalayas(arguments.database)
    if arguments.command == "collect-jobicy":
        return collect_jobicy(arguments.database)
    if arguments.command == "collect-remotive":
        return collect_remotive(arguments.database)
    if arguments.command == "collect-we-work-remotely":
        return collect_we_work_remotely(arguments.database)
    if arguments.command == "analyze-skills":
        return analyze_skills(arguments.database, limit=arguments.limit)
    if arguments.command == "analyze-roles":
        return analyze_roles(arguments.database, limit=arguments.limit)
    if arguments.command == "serve":
        return serve(
            arguments.database,
            host=arguments.host,
            port=arguments.port,
        )

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


def collect_himalayas(database_path: Path) -> int:
    """Run one bounded public Himalayas collection."""

    return _collect_once(
        database_path,
        source_name="Himalayas",
        source_provider=HIMALAYAS_SOURCE_PROVIDER,
        source_scope=HIMALAYAS_SOURCE_SCOPE,
        collector_factory=HimalayasCollector,
        normalizer=normalize_himalayas_job,
    )


def collect_jobicy(database_path: Path) -> int:
    """Run one bounded public Jobicy collection."""

    return _collect_once(
        database_path,
        source_name="Jobicy",
        source_provider=JOBICY_SOURCE_PROVIDER,
        source_scope=JOBICY_SOURCE_SCOPE,
        collector_factory=JobicyCollector,
        normalizer=normalize_jobicy_job,
    )


def collect_remotive(database_path: Path) -> int:
    """Run one bounded public Remotive collection."""

    return _collect_once(
        database_path,
        source_name="Remotive",
        source_provider=REMOTIVE_SOURCE_PROVIDER,
        source_scope=REMOTIVE_SOURCE_SCOPE,
        collector_factory=RemotiveCollector,
        normalizer=normalize_remotive_job,
    )


def collect_we_work_remotely(database_path: Path) -> int:
    """Run one bounded official We Work Remotely RSS collection."""

    return _collect_once(
        database_path,
        source_name="We Work Remotely",
        source_provider=WE_WORK_REMOTELY_SOURCE_PROVIDER,
        source_scope=WE_WORK_REMOTELY_SOURCE_SCOPE,
        collector_factory=WeWorkRemotelyCollector,
        normalizer=normalize_we_work_remotely_job,
    )


def analyze_skills(database_path: Path, *, limit: int) -> int:
    """Run bounded deterministic skill analysis over current SQLite postings."""

    try:
        if not database_path.is_file():
            raise FileNotFoundError(
                f"SQLite database file does not exist: {database_path}"
            )
        with closing(connect_database(database_path)) as connection:
            initialize_database(connection)
            posting_reader = SQLiteJobRepository(connection)
            intelligence_repository = SQLiteSkillIntelligenceRepository(
                connection
            )
            summary = run_skill_smoke(
                posting_reader,
                intelligence_repository,
                limit=limit,
            )
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts failures to exit 1
        print(
            "Skill analysis failed: "
            f"{type(exc).__name__}: {_short_message(exc)}",
            file=sys.stderr,
        )
        return 1

    _print_skill_summary(summary)
    return 0


def analyze_roles(database_path: Path, *, limit: int) -> int:
    """Run bounded deterministic role analysis over current SQLite postings."""

    try:
        if not database_path.is_file():
            raise FileNotFoundError(
                f"SQLite database file does not exist: {database_path}"
            )
        with closing(connect_database(database_path)) as connection:
            initialize_database(connection)
            summary = run_role_smoke(
                SQLiteJobRepository(connection),
                SQLiteRoleIntelligenceRepository(connection),
                limit=limit,
            )
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts failures to exit 1
        print(
            "Role analysis failed: "
            f"{type(exc).__name__}: {_short_message(exc)}",
            file=sys.stderr,
        )
        return 1

    _print_role_summary(summary)
    return 0


def serve(database_path: Path, *, host: str, port: int) -> int:
    """Run the local read-only API against one existing SQLite database."""

    try:
        app = create_app(database_path)
    except DatabaseConfigurationError as exc:
        print(f"API server failed: {exc}", file=sys.stderr)
        return 1

    uvicorn.run(app, host=host, port=port)
    return 0


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
    for command, help_text in (
        ("collect-himalayas", "Run one public Himalayas collection into SQLite."),
        ("collect-jobicy", "Run one public Jobicy collection into SQLite."),
        ("collect-remotive", "Run one public Remotive collection into SQLite."),
        (
            "collect-we-work-remotely",
            "Run one public We Work Remotely RSS collection into SQLite.",
        ),
    ):
        source_parser = subparsers.add_parser(command, help=help_text)
        source_parser.add_argument(
            "--database",
            required=True,
            type=Path,
            metavar="PATH",
            help="SQLite database path to create or reuse.",
        )
    analyze_parser = subparsers.add_parser(
        "analyze-skills",
        help=(
            "Analyze current SQLite postings once with Skill Taxonomy v"
            f"{SKILL_TAXONOMY_VERSION}."
        ),
    )
    analyze_parser.add_argument(
        "--database",
        required=True,
        type=Path,
        metavar="PATH",
        help="Existing SQLite database path to initialize or reuse.",
    )
    analyze_parser.add_argument(
        "--limit",
        default=100,
        type=_positive_int,
        metavar="N",
        help="Maximum current postings to analyze (default: 100).",
    )
    role_parser = subparsers.add_parser(
        "analyze-roles",
        help=(
            "Analyze current SQLite postings once with Role Taxonomy v"
            f"{ROLE_TAXONOMY_VERSION}."
        ),
    )
    role_parser.add_argument(
        "--database",
        required=True,
        type=Path,
        metavar="PATH",
        help="Existing SQLite database path to initialize or reuse.",
    )
    role_parser.add_argument(
        "--limit",
        default=100,
        type=_positive_int,
        metavar="N",
        help="Maximum current postings to analyze (default: 100).",
    )
    serve_parser = subparsers.add_parser(
        "serve",
        help="Run the local read-only Dashboard v0 API.",
    )
    serve_parser.add_argument(
        "--database",
        required=True,
        type=Path,
        metavar="PATH",
        help="Existing current-schema SQLite database path.",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        type=_loopback_host,
        help="Bind host (default: 127.0.0.1).",
    )
    serve_parser.add_argument(
        "--port",
        default=8000,
        type=_port,
        metavar="N",
        help="Bind port from 1 to 65535 (default: 8000).",
    )
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _port(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return parsed


def _loopback_host(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "localhost":
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a loopback host") from exc
    if not address.is_loopback:
        raise argparse.ArgumentTypeError("must be a loopback host")
    return normalized


def _configure_console_streams() -> None:
    """Keep local CLI output usable when Windows encoding lacks a character."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


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


def _print_skill_summary(summary: SkillSmokeSummary) -> None:
    print("Skill analysis completed")
    print()
    print(f"Postings considered: {summary.postings_considered}")
    print(f"New analysis runs: {summary.new_analysis_runs}")
    print(
        "Existing analysis runs reused: "
        f"{summary.existing_analysis_runs_reused}"
    )
    print(f"Evidence records created: {summary.evidence_created}")
    print(f"Zero-skill runs: {summary.zero_skill_runs}")
    print("Failed: 0")

    postings_without_skills = (
        summary.postings_considered - summary.postings_with_skills
    )
    coverage = (
        100 * summary.postings_with_skills / summary.postings_considered
        if summary.postings_considered
        else 0.0
    )
    print()
    print("Posting-level skill coverage:")
    print(f"Postings with at least one skill: {summary.postings_with_skills}")
    print(f"Postings with zero skills: {postings_without_skills}")
    print(f"Coverage: {coverage:.1f}%")

    print()
    print("Top extracted skills (posting-level):")
    if summary.top_skills:
        for item in summary.top_skills[:10]:
            print(f"- {item.name}: {item.postings} posting(s)")
    else:
        print("- none")

    print()
    print("Unrecognized source tags (posting-level):")
    if summary.unrecognized_source_tags:
        for item in summary.unrecognized_source_tags[:10]:
            print(f"- {item.tag}: {item.postings} posting(s)")
    else:
        print("- none")

    print()
    print("Evidence samples (max 10):")
    if not summary.evidence_samples:
        print("- none")
        return
    for sample in summary.evidence_samples:
        print(f"- Skill: {sample.skill_name}")
        print(f"  Field: {sample.evidence_field}")
        print(f"  Matched alias: {sample.matched_alias}")
        print(f"  Job: {sample.job_title}")
        print(f"  Company: {sample.company_name or 'n/a'}")
        print(f"  Evidence: {sample.evidence_text}")


def _print_role_summary(summary: RoleSmokeSummary) -> None:
    print("Role analysis completed")
    print()
    print("Posting-level role coverage:")
    print(f"Postings considered: {summary.postings_considered}")
    print(f"New analysis runs: {summary.new_analysis_runs}")
    print(
        "Existing analysis runs reused: "
        f"{summary.existing_analysis_runs_reused}"
    )
    print(f"Evidence records created: {summary.evidence_created}")
    print(f"Classified postings: {summary.classified_postings}")
    print(f"Unknown postings: {summary.unknown_postings}")
    print(f"Multi-label postings: {summary.multi_label_postings}")
    print("Failed: 0")
    coverage = (
        100 * summary.classified_postings / summary.postings_considered
        if summary.postings_considered
        else 0.0
    )
    print(f"Coverage: {coverage:.1f}%")

    print()
    print("Top extracted roles (distinct postings):")
    if summary.top_roles:
        for item in summary.top_roles[:10]:
            print(
                f"- {item.code} ({item.name}): {item.postings} posting(s)"
            )
    else:
        print("- none")

    print()
    print("Multi-label examples (max 10):")
    if summary.multi_label_samples:
        for sample in summary.multi_label_samples:
            print(f"- Job: {sample.job_title}")
            print(f"  Company: {sample.company_name or 'n/a'}")
            print(f"  Roles: {', '.join(sample.role_codes)}")
    else:
        print("- none")

    print()
    print("Unknown examples (max 10):")
    if summary.unknown_samples:
        for sample in summary.unknown_samples:
            print(f"- Job: {sample.job_title}")
            print(f"  Company: {sample.company_name or 'n/a'}")
    else:
        print("- none")

    print()
    print("Evidence samples (max 10):")
    if not summary.evidence_samples:
        print("- none")
        return
    for sample in summary.evidence_samples:
        print(f"- Role: {sample.role_code} ({sample.role_name})")
        print(f"  Field: {sample.evidence_field}")
        print(f"  Matched: {sample.matched_text}")
        print(f"  Job: {sample.job_title}")
        print(f"  Company: {sample.company_name or 'n/a'}")
        print(f"  Evidence: {sample.evidence_text}")


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
