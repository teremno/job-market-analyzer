import io
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from job_market_analyzer import cli
from job_market_analyzer.collectors.base import CollectedJobs
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.storage.sqlite import connect_database as real_connect_database
from job_market_analyzer.storage.sqlite import initialize_database
from job_market_analyzer.storage.sqlite_backup import DatabaseBackupResult
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

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


def seed_skill_posting(
    database_path: Path,
    external_id: str,
    *,
    title: str,
    description: str | None,
    tags: tuple[str, ...],
) -> None:
    with real_connect_database(database_path) as connection:
        initialize_database(connection)
        posting = NormalizedJobPosting(
            source_provider="remote_ok",
            source_scope="global",
            external_id=external_id,
            source_url=f"https://example.test/jobs/{external_id}",
            title=title,
            company_name=f"Company {external_id}",
            description_text=description,
            source_tags=tags,
            is_remote=True,
        )
        SQLiteJobRepository(connection).persist_observation(
            RawJob(
                source_provider=posting.source_provider,
                source_scope=posting.source_scope,
                external_id=posting.external_id,
                source_url=posting.source_url,
                fetched_at=FETCHED_AT,
                payload={"RAW_PAYLOAD_SECRET": external_id},
            ),
            posting,
        )


def test_cli_help_lists_manual_collection_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert error.value.code == 0
    assert "update" in captured.out
    assert "backup" in captured.out
    assert "collect-remote-ok" in captured.out
    assert "collect-web3-career" in captured.out
    assert "collect-himalayas" in captured.out
    assert "collect-jobicy" in captured.out
    assert "collect-remotive" in captured.out
    assert "collect-we-work-remotely" in captured.out
    assert "analyze-skills" in captured.out
    assert "analyze-roles" in captured.out
    assert "serve" in captured.out
    assert captured.err == ""


def test_backup_requires_database_and_destination(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as missing_database:
        cli.main(["backup"])
    assert missing_database.value.code == 2
    assert "--database" in capsys.readouterr().err

    with pytest.raises(SystemExit) as missing_destination:
        cli.main(["backup", "--database", "jobs.sqlite3"])
    assert missing_destination.value.code == 2
    assert "--destination" in capsys.readouterr().err


def test_backup_dispatches_paths_and_retention(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def backup_spy(
        database_path: Path,
        destination: Path,
        *,
        keep: int,
    ) -> DatabaseBackupResult:
        captured.update(
            database_path=database_path,
            destination=destination,
            keep=keep,
        )
        return DatabaseBackupResult(
            backup_path=Path("backups/jobs.backup-test.sqlite3"),
            retained_count=3,
            removed_count=1,
        )

    monkeypatch.setattr(cli, "create_retained_database_backup", backup_spy)

    exit_code = cli.main(
        [
            "backup",
            "--database",
            "jobs.sqlite3",
            "--destination",
            "backups",
            "--keep",
            "3",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert captured == {
        "database_path": Path("jobs.sqlite3"),
        "destination": Path("backups"),
        "keep": 3,
    }
    assert "Backup completed" in output.out
    assert "Retained backups: 3" in output.out
    assert "Expired backups removed: 1" in output.out
    assert output.err == ""


def test_backup_failure_is_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_backup(*args: object, **kwargs: object) -> DatabaseBackupResult:
        raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr(cli, "create_retained_database_backup", fail_backup)

    exit_code = cli.main(
        [
            "backup",
            "--database",
            "jobs.sqlite3",
            "--destination",
            "backups",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 1
    assert output.out == ""
    assert "Backup failed: RuntimeError: snapshot unavailable" in output.err


@pytest.mark.parametrize("keep", ["0", "-1"])
def test_backup_rejects_non_positive_retention(
    keep: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "backup",
                "--database",
                "jobs.sqlite3",
                "--destination",
                "backups",
                "--keep",
                keep,
            ]
        )

    assert error.value.code == 2
    assert "must be greater than zero" in capsys.readouterr().err


def test_serve_requires_database_and_valid_port(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as missing_database:
        cli.main(["serve"])
    assert missing_database.value.code == 2
    assert "--database" in capsys.readouterr().err

    with pytest.raises(SystemExit) as invalid_port:
        cli.main(["serve", "--database", "jobs.sqlite3", "--port", "70000"])
    assert invalid_port.value.code == 2
    assert "must be between 1 and 65535" in capsys.readouterr().err

    with pytest.raises(SystemExit) as public_host:
        cli.main(["serve", "--database", "jobs.sqlite3", "--host", "0.0.0.0"])
    assert public_host.value.code == 2
    assert "must be a loopback host" in capsys.readouterr().err


def test_serve_dispatches_validated_app_with_local_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    fake_app = object()
    captured: dict[str, object] = {}

    def app_factory(path: Path) -> object:
        captured["database"] = path
        return fake_app

    def run_server(app: object, *, host: str, port: int) -> None:
        captured.update(app=app, host=host, port=port)

    monkeypatch.setattr(cli, "create_app", app_factory)
    monkeypatch.setattr(cli.uvicorn, "run", run_server)

    exit_code = cli.main(["serve", "--database", str(database_path)])

    assert exit_code == 0
    assert captured == {
        "database": database_path,
        "app": fake_app,
        "host": "127.0.0.1",
        "port": 8000,
    }


def test_serve_missing_database_is_nonzero_and_path_safe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "private" / "missing.sqlite3"

    exit_code = cli.main(["serve", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Existing readable SQLite database" in captured.err
    assert str(database_path) not in captured.err


@pytest.mark.parametrize(
    "command",
    [
        "collect-himalayas",
        "collect-jobicy",
        "collect-remotive",
        "collect-we-work-remotely",
    ],
)
def test_public_source_commands_require_explicit_database(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main([command])

    assert error.value.code == 2
    assert "--database" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("command", "function_name"),
    [
        ("collect-himalayas", "collect_himalayas"),
        ("collect-jobicy", "collect_jobicy"),
        ("collect-remotive", "collect_remotive"),
        ("collect-we-work-remotely", "collect_we_work_remotely"),
    ],
)
def test_public_source_commands_dispatch_selected_database(
    command: str,
    function_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected: list[Path] = []

    def command_spy(database_path: Path) -> int:
        selected.append(database_path)
        return 17

    monkeypatch.setattr(cli, function_name, command_spy)

    assert cli.main([command, "--database", "selected.sqlite3"]) == 17
    assert selected == [Path("selected.sqlite3")]


def test_analyze_skills_requires_explicit_database_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["analyze-skills"])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "--database" in captured.err


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_analyze_skills_rejects_non_positive_limit(
    limit: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(
            ["analyze-skills", "--database", "jobs.sqlite3", "--limit", limit]
        )

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "must be greater than zero" in captured.err


def test_analyze_skills_rejects_missing_database_without_creating_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "missing.sqlite3"

    exit_code = cli.main(
        ["analyze-skills", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "SQLite database file does not exist" in captured.err
    assert str(database_path) in captured.err
    assert database_path.exists() is False


def test_analyze_skills_runs_once_is_idempotent_and_prints_safe_bounded_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    description_marker = "FULL_DESCRIPTION_MUST_NOT_BE_PRINTED"
    seed_skill_posting(
        database_path,
        "b",
        title="Python Developer",
        description=f"Python {'x' * 200} {description_marker}",
        tags=("Python", "backend"),
    )
    seed_skill_posting(
        database_path,
        "a",
        title="Customer Support Specialist",
        description="Help customers.",
        tags=("support",),
    )
    seed_skill_posting(
        database_path,
        "c",
        title="Rust Developer",
        description="Write software in Rust.",
        tags=("Rust",),
    )
    connections = install_tracking_connection(monkeypatch)
    real_service = cli.run_skill_smoke
    passed_limits: list[int] = []

    def service_spy(*args: object, limit: int, **kwargs: object):
        passed_limits.append(limit)
        return real_service(*args, limit=limit, **kwargs)

    monkeypatch.setattr(cli, "run_skill_smoke", service_spy)

    first_exit_code = cli.main(
        [
            "analyze-skills",
            "--database",
            str(database_path),
            "--limit",
            "2",
        ]
    )
    first_output = capsys.readouterr()
    second_exit_code = cli.main(
        [
            "analyze-skills",
            "--database",
            str(database_path),
            "--limit",
            "2",
        ]
    )
    second_output = capsys.readouterr()

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert passed_limits == [2, 2]
    assert all(connection.closed for connection in connections)
    assert "Postings considered: 2" in first_output.out
    assert "New analysis runs: 2" in first_output.out
    assert "Zero-skill runs: 1" in first_output.out
    assert "Evidence records created: 3" in first_output.out
    assert "Skill: Python" in first_output.out
    assert "New analysis runs: 0" in second_output.out
    assert "Existing analysis runs reused: 2" in second_output.out
    assert "Evidence records created: 0" in second_output.out
    assert "support: 1 posting(s)" in second_output.out
    assert "Rust Developer" not in first_output.out
    assert description_marker not in first_output.out
    assert "RAW_PAYLOAD_SECRET" not in first_output.out
    assert first_output.err == ""
    assert second_output.err == ""


def test_analyze_skills_returns_nonzero_for_systemic_error_and_closes_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    with real_connect_database(database_path) as connection:
        initialize_database(connection)
    connections = install_tracking_connection(monkeypatch)

    def fail_repository(*args: object, **kwargs: object) -> None:
        raise RuntimeError("repository unavailable")

    monkeypatch.setattr(
        cli.SQLiteJobRepository,
        "list_job_postings",
        fail_repository,
    )

    exit_code = cli.main(
        [
            "analyze-skills",
            "--database",
            str(database_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Skill analysis failed: RuntimeError: repository unavailable" in captured.err
    assert connections[0].closed is True


def test_analyze_skills_replaces_unencodable_console_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    seed_skill_posting(
        database_path,
        "unicode",
        title="Python Developer",
        description="Use Python\x00 daily.",
        tags=(),
    )
    output_bytes = io.BytesIO()
    output = io.TextIOWrapper(output_bytes, encoding="cp1251")
    monkeypatch.setattr(sys, "stdout", output)

    exit_code = cli.main(
        ["analyze-skills", "--database", str(database_path)]
    )
    output.flush()
    rendered = output_bytes.getvalue().decode("cp1251")

    assert exit_code == 0
    assert "Skill analysis completed" in rendered
    assert "Evidence: Use Python? daily." in rendered


def test_analyze_roles_requires_explicit_database_and_positive_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as missing_database:
        cli.main(["analyze-roles"])
    assert missing_database.value.code == 2
    assert "--database" in capsys.readouterr().err

    with pytest.raises(SystemExit) as invalid_limit:
        cli.main(
            ["analyze-roles", "--database", "jobs.sqlite3", "--limit", "0"]
        )
    assert invalid_limit.value.code == 2
    assert "must be greater than zero" in capsys.readouterr().err


def test_analyze_roles_rejects_missing_database_without_creating_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "missing.sqlite3"

    exit_code = cli.main(["analyze-roles", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "SQLite database file does not exist" in captured.err
    assert database_path.exists() is False


def test_analyze_roles_runs_once_reuses_and_prints_bounded_safe_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    seed_skill_posting(
        database_path,
        "a",
        title="Backend / Platform Engineer",
        description="FULL_DESCRIPTION_MUST_NOT_BE_PRINTED",
        tags=(),
    )
    seed_skill_posting(
        database_path,
        "b",
        title="Software Engineer",
        description=None,
        tags=(),
    )
    connections = install_tracking_connection(monkeypatch)

    first = cli.main(
        ["analyze-roles", "--database", str(database_path), "--limit", "2"]
    )
    first_output = capsys.readouterr()
    second = cli.main(
        ["analyze-roles", "--database", str(database_path), "--limit", "2"]
    )
    second_output = capsys.readouterr()

    assert first == second == 0
    assert all(connection.closed for connection in connections)
    assert "Role analysis completed" in first_output.out
    assert "Postings considered: 2" in first_output.out
    assert "New analysis runs: 2" in first_output.out
    assert "Classified postings: 1" in first_output.out
    assert "Unknown postings: 1" in first_output.out
    assert "Multi-label postings: 1" in first_output.out
    assert "Evidence records created: 2" in first_output.out
    assert "Roles: backend, devops_platform" in first_output.out
    assert "FULL_DESCRIPTION_MUST_NOT_BE_PRINTED" not in first_output.out
    assert "RAW_PAYLOAD_SECRET" not in first_output.out
    assert "New analysis runs: 0" in second_output.out
    assert "Existing analysis runs reused: 2" in second_output.out
    assert "Evidence records created: 0" in second_output.out
    assert first_output.err == second_output.err == ""


def test_analyze_roles_systemic_failure_is_nonzero_and_closes_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    with real_connect_database(database_path) as connection:
        initialize_database(connection)
    connections = install_tracking_connection(monkeypatch)

    def fail_repository(*args: object, **kwargs: object) -> None:
        raise RuntimeError("repository unavailable")

    monkeypatch.setattr(
        cli.SQLiteJobRepository,
        "list_job_postings",
        fail_repository,
    )

    exit_code = cli.main(["analyze-roles", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Role analysis failed: RuntimeError: repository unavailable" in captured.err
    assert connections[0].closed is True


def test_analyze_roles_replaces_unencodable_console_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    seed_skill_posting(
        database_path,
        "unicode",
        title="Security Engineer – Infrastructure 🚀",
        description=None,
        tags=(),
    )
    output_bytes = io.BytesIO()
    output = io.TextIOWrapper(output_bytes, encoding="cp1251")
    monkeypatch.setattr(sys, "stdout", output)

    exit_code = cli.main(["analyze-roles", "--database", str(database_path)])
    output.flush()
    rendered = output_bytes.getvalue().decode("cp1251")

    assert exit_code == 0
    assert "Role analysis completed" in rendered
    assert "Security Engineer – Infrastructure ?" in rendered


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


def test_serve_accepts_any_ipv4_host_only_with_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    # Without the opt-in, non-loopback hosts stay rejected.
    with pytest.raises(SystemExit) as rejected:
        cli.main(["serve", "--database", "jobs.sqlite3", "--host", "0.0.0.0"])
    assert rejected.value.code == 2

    monkeypatch.setenv("JMA_SERVE_ALLOW_ANY_HOST", "1")
    parser = cli._build_parser()
    args = parser.parse_args(
        ["serve", "--database", "jobs.sqlite3", "--host", "0.0.0.0"]
    )
    assert args.host == "0.0.0.0"

    # IPv6 stays loopback-only even with the opt-in.
    with pytest.raises(SystemExit) as v6_rejected:
        parser.parse_args(["serve", "--host", "::"])
    assert v6_rejected.value.code == 2
