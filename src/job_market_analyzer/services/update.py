"""Guided one-shot collection and intelligence orchestration."""

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from job_market_analyzer.analytics.models import AnalyticsOverview
from job_market_analyzer.analytics.sqlite_repository import SQLiteAnalyticsRepository
from job_market_analyzer.collectors.base import JobCollector
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.services.collection import (
    CollectionSummary,
    persist_collected_jobs,
)
from job_market_analyzer.storage.repository import (
    SourceUpdateRunRecord,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

JobNormalizer = Callable[[RawJob], NormalizedJobPosting]
CollectorFactory = Callable[[], JobCollector]


@dataclass(frozen=True, slots=True)
class SourceAdapter:
    """One explicitly registered source usable by the guided update flow."""

    provider_code: str
    display_name: str
    collector_factory: CollectorFactory
    normalizer: JobNormalizer
    credential_env: str | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AnalyzerExecutionSummary:
    """Language-specific analyzer counts normalized for orchestration output."""

    postings_considered: int
    runs_created: int
    runs_reused: int


AnalyzerRunner = Callable[
    [sqlite3.Connection, int],
    AnalyzerExecutionSummary,
]


@dataclass(frozen=True, slots=True)
class AnalyzerAdapter:
    """One analyzer implementation for a stable kind and input language."""

    kind: str
    display_name: str
    language: str
    version: str
    runner: AnalyzerRunner


class SourceRunStatus(StrEnum):
    """Visible outcome of one independent source run."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class AnalyzerRunStatus(StrEnum):
    """Visible outcome of one independent analyzer run."""

    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SourceUpdateResult:
    """Safe summary for one registered source."""

    provider_code: str
    display_name: str
    status: SourceRunStatus
    collection: CollectionSummary | None = None
    message: str | None = None

    @property
    def changed_postings(self) -> int:
        """Return changed existing postings that created raw provenance."""

        if self.collection is None:
            return 0
        return (
            self.collection.raw_observations_created
            - self.collection.postings_created
        )


@dataclass(frozen=True, slots=True)
class AnalyzerUpdateResult:
    """Safe summary for one language-specific analyzer."""

    kind: str
    display_name: str
    language: str
    version: str
    status: AnalyzerRunStatus
    execution: AnalyzerExecutionSummary | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class GuidedUpdateSummary:
    """Complete result of one guided update execution."""

    analysis_language: str
    sources: tuple[SourceUpdateResult, ...]
    analyzers: tuple[AnalyzerUpdateResult, ...]
    dataset: AnalyticsOverview

    @property
    def has_failures(self) -> bool:
        """Whether the completed run had visible source or analyzer failures."""

        return any(
            result.status is SourceRunStatus.FAILED
            or (
                result.collection is not None
                and result.collection.failed > 0
            )
            for result in self.sources
        ) or any(
            result.status is AnalyzerRunStatus.FAILED
            for result in self.analyzers
        )


class UnsupportedAnalyzerLanguageError(ValueError):
    """Raised before collection when active analyzers lack a requested language."""


def select_analyzers(
    analyzers: Sequence[AnalyzerAdapter],
    *,
    language: str,
) -> tuple[AnalyzerAdapter, ...]:
    """Return one complete language implementation for every analyzer kind."""

    required_kinds = {adapter.kind for adapter in analyzers}
    selected = tuple(
        adapter for adapter in analyzers if adapter.language == language
    )
    selected_kinds = {adapter.kind for adapter in selected}
    missing = sorted(required_kinds - selected_kinds)
    if missing:
        language_name = {"en": "English", "uk": "Ukrainian"}.get(
            language,
            language,
        )
        raise UnsupportedAnalyzerLanguageError(
            f"{language_name} intelligence extraction is not implemented yet "
            f"for: {', '.join(missing)}"
        )
    return selected


async def run_guided_update(
    connection: sqlite3.Connection,
    *,
    sources: Sequence[SourceAdapter],
    analyzers: Sequence[AnalyzerAdapter],
    analysis_language: str,
    analysis_limit: int | None,
    environment: Mapping[str, str],
) -> GuidedUpdateSummary:
    """Collect independent sources, analyze current postings, and summarize."""

    selected_analyzers = select_analyzers(
        analyzers,
        language=analysis_language,
    )
    repository = SQLiteJobRepository(connection)
    source_results: list[SourceUpdateResult] = []

    for source in sources:
        run_started_at = datetime.now(UTC)
        credential = (
            environment.get(source.credential_env, "").strip()
            if source.credential_env is not None
            else ""
        )
        if source.credential_env is not None and not credential:
            message = f"{source.credential_env} is not configured"
            repository.record_source_update_run(
                SourceUpdateRunRecord(
                    source_provider=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.SKIPPED.value,
                    started_at=run_started_at,
                    finished_at=_finished_clock(run_started_at),
                    message=message,
                )
            )
            source_results.append(
                SourceUpdateResult(
                    provider_code=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.SKIPPED,
                    message=message,
                )
            )
            continue

        try:
            collected = await source.collector_factory().collect()
        except Exception as exc:  # noqa: BLE001 - isolated remote-source boundary
            failure_message = _safe_exception_message(
                exc,
                sensitive_values=(credential,),
            )
            repository.record_source_update_run(
                SourceUpdateRunRecord(
                    source_provider=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.FAILED.value,
                    started_at=run_started_at,
                    finished_at=_finished_clock(run_started_at),
                    message=failure_message,
                )
            )
            source_results.append(
                SourceUpdateResult(
                    provider_code=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.FAILED,
                    message=failure_message,
                )
            )
            continue

        try:
            collection = persist_collected_jobs(
                collected,
                source.normalizer,
                repository,
            )
        except Exception as exc:  # noqa: BLE001 - isolated persistence boundary
            if connection.in_transaction:
                raise RuntimeError(
                    f"source {source.provider_code!r} left an active transaction"
                ) from exc
            failure_message = _safe_exception_message(exc)
            repository.record_source_update_run(
                SourceUpdateRunRecord(
                    source_provider=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.FAILED.value,
                    started_at=run_started_at,
                    finished_at=_finished_clock(run_started_at),
                    message=failure_message,
                )
            )
            source_results.append(
                SourceUpdateResult(
                    provider_code=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.FAILED,
                    message=failure_message,
                )
            )
            continue

        if connection.in_transaction:
            raise RuntimeError(
                f"source {source.provider_code!r} left an active transaction"
            )
        history_note: str | None = None
        try:
            repository.record_source_update_run(
                SourceUpdateRunRecord(
                    source_provider=source.provider_code,
                    display_name=source.display_name,
                    status=SourceRunStatus.COMPLETED.value,
                    started_at=run_started_at,
                    finished_at=_finished_clock(run_started_at),
                    fetched_count=collection.fetched,
                    persisted_count=collection.persisted,
                    failed_count=collection.failed,
                )
            )
        except sqlite3.Error as exc:  # noqa: BLE001 - history is best-effort
            history_note = (
                "postings persisted but update-run history write failed: "
                f"{_safe_exception_message(exc)}"
            )
        source_results.append(
            SourceUpdateResult(
                provider_code=source.provider_code,
                display_name=source.display_name,
                status=SourceRunStatus.COMPLETED,
                collection=collection,
                message=history_note,
            )
        )

    posting_count = int(
        connection.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
    )
    effective_limit = (
        max(posting_count, 1) if analysis_limit is None else analysis_limit
    )
    analyzer_results: list[AnalyzerUpdateResult] = []
    for analyzer in selected_analyzers:
        try:
            execution = analyzer.runner(connection, effective_limit)
        except sqlite3.Error as exc:
            if connection.in_transaction:
                raise RuntimeError(
                    f"analyzer {analyzer.kind!r} left an active transaction"
                ) from exc
            raise
        except Exception as exc:  # noqa: BLE001 - visible analyzer failure boundary
            if connection.in_transaction:
                raise RuntimeError(
                    f"analyzer {analyzer.kind!r} left an active transaction"
                ) from exc
            analyzer_results.append(
                AnalyzerUpdateResult(
                    kind=analyzer.kind,
                    display_name=analyzer.display_name,
                    language=analyzer.language,
                    version=analyzer.version,
                    status=AnalyzerRunStatus.FAILED,
                    message=_safe_exception_message(exc),
                )
            )
            continue
        analyzer_results.append(
            AnalyzerUpdateResult(
                kind=analyzer.kind,
                display_name=analyzer.display_name,
                language=analyzer.language,
                version=analyzer.version,
                status=AnalyzerRunStatus.COMPLETED,
                execution=execution,
            )
        )

    dataset = SQLiteAnalyticsRepository(connection).get_overview()
    return GuidedUpdateSummary(
        analysis_language=analysis_language,
        sources=tuple(source_results),
        analyzers=tuple(analyzer_results),
        dataset=dataset,
    )


def _finished_clock(started_at: datetime) -> datetime:
    """Return a monotonic-safe UTC finish timestamp for one attempt."""

    now = datetime.now(UTC)
    return now if now >= started_at else started_at


def _safe_exception_message(
    exception: Exception,
    *,
    sensitive_values: Sequence[str] = (),
) -> str:
    message = str(exception).splitlines()[0].strip() or type(exception).__name__
    for sensitive_value in sensitive_values:
        if sensitive_value:
            message = message.replace(sensitive_value, "[REDACTED]")
    if len(message) > 240:
        message = f"{message[:237].rstrip()}..."
    return f"{type(exception).__name__}: {message}"
