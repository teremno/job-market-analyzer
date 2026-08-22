from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from job_market_analyzer import cli
from job_market_analyzer.collectors.base import CollectedJobs
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.services.update import (
    AnalyzerAdapter,
    SourceAdapter,
)
from job_market_analyzer.services.update_registry import ANALYZER_REGISTRY
from job_market_analyzer.services.update_registry import SOURCE_REGISTRY as REAL_SOURCE_REGISTRY
from job_market_analyzer.storage.sqlite import connect_database

FETCHED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
FAKE_TOKEN = "fake-update-token-do-not-log"


class StaticCollector:
    def __init__(self, raw_job: RawJob) -> None:
        self.raw_job = raw_job
        self.calls = 0

    async def collect(self) -> CollectedJobs:
        self.calls += 1
        fetched_at = FETCHED_AT + timedelta(minutes=self.calls)
        return CollectedJobs(
            fetched=1,
            jobs=(self.raw_job.model_copy(update={"fetched_at": fetched_at}),),
        )


class FailingCollector:
    def __init__(self, message: str) -> None:
        self.message = message
        self.calls = 0

    async def collect(self) -> CollectedJobs:
        self.calls += 1
        raise RuntimeError(self.message)


def make_source(
    provider: str,
    collector: StaticCollector | FailingCollector,
    *,
    credential_env: str | None = None,
) -> SourceAdapter:
    return SourceAdapter(
        provider_code=provider,
        display_name=provider.replace("_", " ").title(),
        collector_factory=lambda: collector,
        normalizer=normalize_test_job,
        credential_env=credential_env,
    )


def make_raw_job(provider: str, external_id: str = "job-1") -> RawJob:
    return RawJob(
        source_provider=provider,
        source_scope="global",
        external_id=external_id,
        source_url=f"https://example.test/{provider}/{external_id}",
        fetched_at=FETCHED_AT,
        payload={
            "title": "Senior Python Engineer",
            "company": "Example Company",
            "description": "Build Python APIs with PostgreSQL.",
            "tags": ["Python", "PostgreSQL"],
        },
    )


def normalize_test_job(raw_job: RawJob) -> NormalizedJobPosting:
    return NormalizedJobPosting(
        source_provider=raw_job.source_provider,
        source_scope=raw_job.source_scope,
        external_id=raw_job.external_id,
        source_url=raw_job.source_url,
        title=str(raw_job.payload["title"]),
        company_name=str(raw_job.payload["company"]),
        description_text=str(raw_job.payload["description"]),
        source_tags=tuple(raw_job.payload["tags"]),
        is_remote=True,
    )


def database_counts(database_path: Path) -> tuple[int, int, int, int, int]:
    with connect_database(database_path) as connection:
        base_counts = tuple(
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("canonical_jobs", "job_postings", "raw_jobs")
        )
        analysis_counts = tuple(
            int(
                connection.execute(
                    "SELECT COUNT(*) FROM analysis_runs WHERE analyzer_kind = ?",
                    (kind,),
                ).fetchone()[0]
            )
            for kind in ("skills", "roles")
        )
        return (*base_counts, *analysis_counts)


def test_update_runs_sources_in_registry_order_skips_missing_token_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    call_order: list[str] = []

    class OrderedCollector(StaticCollector):
        async def collect(self) -> CollectedJobs:
            call_order.append(self.raw_job.source_provider)
            return await super().collect()

    providers = ("remote_ok", "web3_career", "himalayas", "jobicy", "remotive", "wwr")
    collectors = {
        provider: OrderedCollector(make_raw_job(provider)) for provider in providers
    }
    sources = tuple(
        make_source(
            provider,
            collectors[provider],
            credential_env=("WEB3_CAREER_API_TOKEN" if provider == "web3_career" else None),
        )
        for provider in providers
    )
    monkeypatch.setattr(cli, "SOURCE_REGISTRY", sources)
    monkeypatch.delenv("WEB3_CAREER_API_TOKEN", raising=False)

    first_exit = cli.main(["update", "--database", str(database_path)])
    first_output = capsys.readouterr()
    first_counts = database_counts(database_path)

    second_exit = cli.main(["update", "--database", str(database_path)])
    second_output = capsys.readouterr()
    second_counts = database_counts(database_path)

    expected_order = [provider for provider in providers if provider != "web3_career"]
    assert first_exit == second_exit == 0
    assert call_order == expected_order * 2
    assert "Web3 Career: SKIPPED - WEB3_CAREER_API_TOKEN is not configured" in first_output.out
    assert first_output.out.count("1 fetched, 1 new") == 5
    assert "0 new" in second_output.out
    assert "0 changed" in second_output.out
    assert "5 reused" in second_output.out
    assert first_counts == second_counts == (5, 5, 5, 5, 5)
    assert first_output.err == second_output.err == ""


def test_update_continues_after_source_failure_and_analyzes_persisted_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failed = FailingCollector("temporary source failure")
    successful = StaticCollector(make_raw_job("healthy_source"))
    monkeypatch.setattr(
        cli,
        "SOURCE_REGISTRY",
        (
            make_source("failed_source", failed),
            make_source("healthy_source", successful),
        ),
    )

    exit_code = cli.main(
        ["update", "--database", str(tmp_path / "jobs.sqlite3")]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert failed.calls == successful.calls == 1
    assert "Failed Source: FAILED - RuntimeError: temporary source failure" in captured.out
    assert "Healthy Source: 1 fetched, 1 new" in captured.out
    assert "Skills: 1 considered" in captured.out
    assert "Roles: 1 considered" in captured.out
    assert captured.err == ""


def test_update_rejects_unsupported_language_before_database_or_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "must-not-exist.sqlite3"
    collector = StaticCollector(make_raw_job("remote_ok"))
    monkeypatch.setattr(cli, "SOURCE_REGISTRY", (make_source("remote_ok", collector),))

    exit_code = cli.main(
        ["update", "--database", str(database_path), "--language", "uk"]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert collector.calls == 0
    assert not database_path.exists()
    assert "Ukrainian intelligence extraction is not implemented yet" in captured.err
    assert "geography, roles, salary, seniority, skills" in captured.err


def test_update_rejects_unknown_source_as_argument_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "update",
                "--database",
                str(tmp_path / "jobs.sqlite3"),
                "--source",
                "unknown",
            ]
        )

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_update_requires_explicit_database(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["update"])

    assert error.value.code == 2
    assert "--database" in capsys.readouterr().err


def test_update_source_filter_uses_registry_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = StaticCollector(make_raw_job("first"))
    second = StaticCollector(make_raw_job("second"))
    monkeypatch.setattr(
        cli,
        "SOURCE_REGISTRY",
        (make_source("first", first), make_source("second", second)),
    )

    exit_code = cli.main(
        [
            "update",
            "--database",
            str(tmp_path / "jobs.sqlite3"),
            "--source",
            "second",
        ]
    )

    assert exit_code == 0
    assert first.calls == 0
    assert second.calls == 1


def test_update_aborts_on_malformed_database_before_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "malformed.sqlite3"
    database_path.write_bytes(b"not a sqlite database")
    collector = StaticCollector(make_raw_job("remote_ok"))
    monkeypatch.setattr(cli, "SOURCE_REGISTRY", (make_source("remote_ok", collector),))

    exit_code = cli.main(["update", "--database", str(database_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert collector.calls == 0
    assert "Update failed: DatabaseError:" in captured.err


def test_update_aborts_remaining_sources_on_systemic_persistence_path_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = StaticCollector(make_raw_job("first"))
    second = StaticCollector(make_raw_job("second"))

    def broken_normalizer(_raw_job: RawJob) -> NormalizedJobPosting:
        raise RuntimeError("unexpected normalization invariant failure")

    monkeypatch.setattr(
        cli,
        "SOURCE_REGISTRY",
        (
            SourceAdapter("first", "First", lambda: first, broken_normalizer),
            make_source("second", second),
        ),
    )

    exit_code = cli.main(["update", "--database", str(tmp_path / "jobs.sqlite3")])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert first.calls == 1
    assert second.calls == 0
    assert "Update failed: RuntimeError: unexpected normalization invariant failure" in captured.err


def test_update_reports_analyzer_failure_without_hiding_successful_analyzer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_analyzer(_connection: object, _limit: int) -> object:
        raise RuntimeError("analyzer unavailable")

    failing_roles = AnalyzerAdapter(
        kind="roles",
        display_name="Roles",
        language="en",
        version="test",
        runner=fail_analyzer,
    )
    monkeypatch.setattr(cli, "SOURCE_REGISTRY", ())
    monkeypatch.setattr(
        cli,
        "ANALYZER_REGISTRY",
        (ANALYZER_REGISTRY[0], failing_roles),
    )

    exit_code = cli.main(["update", "--database", str(tmp_path / "jobs.sqlite3")])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Skills: 0 considered" in captured.out
    assert "Roles: FAILED - RuntimeError: analyzer unavailable" in captured.out


def test_update_redacts_credential_from_source_and_systemic_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    collector = FailingCollector(f"request rejected for token {FAKE_TOKEN}")
    monkeypatch.setenv("WEB3_CAREER_API_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(
        cli,
        "SOURCE_REGISTRY",
        (
            make_source(
                "web3_career",
                collector,
                credential_env="WEB3_CAREER_API_TOKEN",
            ),
        ),
    )

    exit_code = cli.main(["update", "--database", str(tmp_path / "jobs.sqlite3")])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "[REDACTED]" in captured.out
    assert FAKE_TOKEN not in captured.out
    assert FAKE_TOKEN not in captured.err


def test_current_registries_have_exact_source_and_english_analyzer_capabilities() -> None:
    assert tuple(source.provider_code for source in REAL_SOURCE_REGISTRY) == (
        "remote_ok",
        "web3_career",
        "himalayas",
        "jobicy",
        "remotive",
        "we_work_remotely",
        "greenhouse",
        "lever",
        "ashby",
    )
    assert len({source.provider_code for source in REAL_SOURCE_REGISTRY}) == 9
    assert {(analyzer.kind, analyzer.language) for analyzer in ANALYZER_REGISTRY} == {
        ("skills", "en"),
        ("roles", "en"),
        ("seniority", "en"),
        ("geography", "en"),
        ("salary", "en"),
    }
