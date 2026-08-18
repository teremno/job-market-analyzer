import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from job_market_analyzer import cli
from job_market_analyzer.collectors.base import CollectedJobs
from job_market_analyzer.models import RawJob
from job_market_analyzer.storage.sqlite import connect_database as real_connect_database

FETCHED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
FAKE_WEB3_TOKEN = "offline-test-token"


class StaticCollector:
    def __init__(self, jobs: tuple[RawJob, ...]) -> None:
        self._jobs = jobs

    async def collect(self) -> CollectedJobs:
        return CollectedJobs(fetched=len(self._jobs), jobs=self._jobs)


class FailingCollector:
    def __init__(self, message: str = "source unavailable") -> None:
        self._message = message

    async def collect(self) -> CollectedJobs:
        raise RuntimeError(self._message)


class TrackingConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.closed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def close(self) -> None:
        self.closed = True
        self._connection.close()


def make_raw_job(external_id: str, *, title: str | None) -> RawJob:
    payload: dict[str, object] = {
        "id": external_id,
        "company": "Example Company",
        "description": "Description must not be printed.",
        "location": "Worldwide",
        "url": f"https://remoteok.com/remote-jobs/{external_id}",
    }
    if title is not None:
        payload["position"] = title

    return RawJob(
        source_provider="remote_ok",
        source_scope="global",
        external_id=external_id,
        source_url=payload["url"],
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def make_web3_raw_job(external_id: str, *, title: str | None) -> RawJob:
    source_url = f"https://web3.career/job/{external_id}"
    payload: dict[str, object] = {
        "id": external_id,
        "company": "Web3 Example",
        "description": "Private description must not be printed.",
        "location": "Worldwide",
        "remote": True,
        "url": source_url,
        "apply_url": f"https://web3.career/apply/{external_id}",
    }
    if title is not None:
        payload["title"] = title

    return RawJob(
        source_provider="web3_career",
        source_scope="global",
        external_id=external_id,
        source_url=source_url,
        fetched_at=FETCHED_AT,
        payload=payload,
    )


def install_tracking_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> list[TrackingConnection]:
    connections: list[TrackingConnection] = []

    def connect(database_path: Path) -> TrackingConnection:
        connection = TrackingConnection(real_connect_database(database_path))
        connections.append(connection)
        return connection

    monkeypatch.setattr(cli, "connect_database", connect)
    return connections


def test_cli_help_lists_manual_collection_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert error.value.code == 0
    assert "collect-remote-ok" in captured.out
    assert "collect-web3-career" in captured.out
    assert captured.err == ""


def test_collect_remote_ok_requires_explicit_database_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["collect-remote-ok"])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "--database" in captured.err


def test_collect_remote_ok_wires_pipeline_and_prints_success_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    collector = StaticCollector((make_raw_job("job-1", title="Python Developer"),))
    connections = install_tracking_connection(monkeypatch)
    monkeypatch.setattr(cli, "RemoteOKCollector", lambda: collector)
    real_service = cli.collect_and_persist_jobs
    wiring: dict[str, object] = {}

    async def service_spy(
        passed_collector: object,
        normalizer: object,
        repository: object,
    ):
        wiring.update(
            collector=passed_collector,
            normalizer=normalizer,
            repository=repository,
        )
        return await real_service(passed_collector, normalizer, repository)

    monkeypatch.setattr(cli, "collect_and_persist_jobs", service_spy)

    exit_code = cli.main(
        ["collect-remote-ok", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert wiring["collector"] is collector
    assert wiring["normalizer"] is cli.normalize_remote_ok_job
    assert isinstance(wiring["repository"], cli.SQLiteJobRepository)
    assert connections[0].closed is True
    assert "Remote OK collection completed" in captured.out
    assert "Fetched: 1" in captured.out
    assert "Persisted: 1" in captured.out
    assert "Postings created: 1" in captured.out
    assert "Raw observations created: 1" in captured.out
    assert "Failed: 0" in captured.out
    assert "Canonical jobs: 1" in captured.out
    assert "Job postings: 1" in captured.out
    assert "Raw observations: 1" in captured.out
    assert "Python Developer" in captured.out
    assert "Example Company" in captured.out
    assert "Worldwide" in captured.out
    assert "https://remoteok.com/remote-jobs/job-1" in captured.out
    assert "Description must not be printed" not in captured.out
    assert captured.err == ""


def test_collect_remote_ok_returns_nonzero_for_recoverable_item_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    collector = StaticCollector(
        (
            make_raw_job("missing-title", title=None),
            make_raw_job("valid", title="Valid Job"),
        )
    )
    monkeypatch.setattr(cli, "RemoteOKCollector", lambda: collector)

    exit_code = cli.main(
        ["collect-remote-ok", "--database", str(tmp_path / "jobs.sqlite3")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Fetched: 2" in captured.out
    assert "Persisted: 1" in captured.out
    assert "Failed: 1" in captured.out
    assert "Failures:" in captured.out
    assert "normalize (missing-title)" in captured.out
    assert captured.err == ""


def test_collect_remote_ok_reuses_existing_database_without_duplicate_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    collector = StaticCollector((make_raw_job("stable", title="Stable Job"),))
    monkeypatch.setattr(cli, "RemoteOKCollector", lambda: collector)

    first_exit_code = cli.main(
        ["collect-remote-ok", "--database", str(database_path)]
    )
    capsys.readouterr()
    second_exit_code = cli.main(
        ["collect-remote-ok", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert first_exit_code == 0
    assert second_exit_code == 0
    assert "Postings created: 0" in captured.out
    assert "Raw observations created: 0" in captured.out
    assert "Canonical jobs: 1" in captured.out
    assert "Job postings: 1" in captured.out
    assert "Raw observations: 1" in captured.out
    assert captured.err == ""


def test_collect_remote_ok_returns_nonzero_for_systemic_exception_and_closes_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connections = install_tracking_connection(monkeypatch)
    monkeypatch.setattr(cli, "RemoteOKCollector", FailingCollector)

    exit_code = cli.main(
        ["collect-remote-ok", "--database", str(tmp_path / "jobs.sqlite3")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Remote OK collection failed: RuntimeError: source unavailable" in captured.err
    assert connections[0].closed is True


def test_collect_web3_career_requires_explicit_database_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["collect-web3-career"])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "--database" in captured.err


def test_collect_web3_career_requires_token_environment_variable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    monkeypatch.delenv(cli.WEB3_CAREER_TOKEN_ENV, raising=False)

    exit_code = cli.main(
        ["collect-web3-career", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert cli.WEB3_CAREER_TOKEN_ENV in captured.err
    assert database_path.exists() is False


def test_collect_web3_career_wires_pipeline_prints_safe_summary_and_closes_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    collector = StaticCollector(
        (make_web3_raw_job("job-1", title="Smart Contract Engineer"),)
    )
    connections = install_tracking_connection(monkeypatch)
    monkeypatch.setenv(cli.WEB3_CAREER_TOKEN_ENV, FAKE_WEB3_TOKEN)
    monkeypatch.setattr(cli, "Web3CareerCollector", lambda: collector)
    real_service = cli.collect_and_persist_jobs
    wiring: dict[str, object] = {}

    async def service_spy(
        passed_collector: object,
        normalizer: object,
        repository: object,
    ):
        wiring.update(
            collector=passed_collector,
            normalizer=normalizer,
            repository=repository,
        )
        return await real_service(passed_collector, normalizer, repository)

    monkeypatch.setattr(cli, "collect_and_persist_jobs", service_spy)

    exit_code = cli.main(
        ["collect-web3-career", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert wiring["collector"] is collector
    assert wiring["normalizer"] is cli.normalize_web3_career_job
    assert isinstance(wiring["repository"], cli.SQLiteJobRepository)
    assert connections[0].closed is True
    assert "Web3.career collection completed" in captured.out
    assert "Fetched: 1" in captured.out
    assert "Persisted: 1" in captured.out
    assert "Postings created: 1" in captured.out
    assert "Raw observations created: 1" in captured.out
    assert "Failed: 0" in captured.out
    assert "Canonical jobs: 1" in captured.out
    assert "Job postings: 1" in captured.out
    assert "Raw observations: 1" in captured.out
    assert "Smart Contract Engineer" in captured.out
    assert "Web3 Example" in captured.out
    assert "Worldwide" in captured.out
    assert "https://web3.career/job/job-1" in captured.out
    assert "https://web3.career/apply/job-1" in captured.out
    assert "Private description must not be printed" not in captured.out
    assert FAKE_WEB3_TOKEN not in captured.out
    assert FAKE_WEB3_TOKEN not in captured.err
    assert FAKE_WEB3_TOKEN not in caplog.text
    assert captured.err == ""


def test_collect_web3_career_returns_nonzero_for_recoverable_failure_and_redacts_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    collector = StaticCollector(
        (
            make_web3_raw_job(FAKE_WEB3_TOKEN, title=None),
            make_web3_raw_job("valid", title="Valid Web3 Job"),
        )
    )
    monkeypatch.setenv(cli.WEB3_CAREER_TOKEN_ENV, FAKE_WEB3_TOKEN)
    monkeypatch.setattr(cli, "Web3CareerCollector", lambda: collector)

    exit_code = cli.main(
        ["collect-web3-career", "--database", str(tmp_path / "jobs.sqlite3")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Fetched: 2" in captured.out
    assert "Persisted: 1" in captured.out
    assert "Failed: 1" in captured.out
    assert "Failures:" in captured.out
    assert "normalize ([REDACTED])" in captured.out
    assert FAKE_WEB3_TOKEN not in captured.out
    assert FAKE_WEB3_TOKEN not in captured.err


def test_collect_web3_career_returns_nonzero_for_systemic_exception_and_closes_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connections = install_tracking_connection(monkeypatch)
    monkeypatch.setenv(cli.WEB3_CAREER_TOKEN_ENV, FAKE_WEB3_TOKEN)
    monkeypatch.setattr(
        cli,
        "Web3CareerCollector",
        lambda: FailingCollector(f"source rejected {FAKE_WEB3_TOKEN}"),
    )

    exit_code = cli.main(
        ["collect-web3-career", "--database", str(tmp_path / "jobs.sqlite3")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Web3.career collection failed: RuntimeError" in captured.err
    assert "source rejected [REDACTED]" in captured.err
    assert FAKE_WEB3_TOKEN not in captured.err
    assert connections[0].closed is True
