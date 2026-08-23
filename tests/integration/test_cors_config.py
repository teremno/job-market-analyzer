"""CORS origin configuration tests for public deployments."""

from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from job_market_analyzer.api import create_app
from job_market_analyzer.storage.sqlite import connect_database, initialize_database


@pytest.fixture
def api_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "cors.sqlite3"
    with closing(connect_database(database_path)) as connection:
        initialize_database(connection)
    return database_path


def _cors_headers(app, origin: str):
    with TestClient(app) as client:
        response = client.get(
            "/api/health",
            headers={"Origin": origin},
        )
        return response.headers.get("access-control-allow-origin")


def test_default_allows_only_local_dashboard_origins(api_database, monkeypatch):
    monkeypatch.delenv("JMA_CORS_ORIGINS", raising=False)
    app = create_app(api_database)
    assert _cors_headers(app, "http://localhost:3000") == "http://localhost:3000"
    assert _cors_headers(app, "http://127.0.0.1:3000") == "http://127.0.0.1:3000"
    assert _cors_headers(app, "https://example.com") is None


def test_env_override_adds_public_origin_and_keeps_defaults(api_database, monkeypatch):
    monkeypatch.setenv(
        "JMA_CORS_ORIGINS", "https://jobs.example.com, http://localhost:3000,"
    )
    app = create_app(api_database)
    assert _cors_headers(app, "https://jobs.example.com") == "https://jobs.example.com"
    assert _cors_headers(app, "http://localhost:3000") == "http://localhost:3000"
    # Unlisted origins stay rejected.
    assert _cors_headers(app, "https://evil.example") is None


def test_wildcard_is_rejected_silently_keeping_safe_default(api_database, monkeypatch):
    monkeypatch.setenv("JMA_CORS_ORIGINS", "*, https://jobs.example.com")
    app = create_app(api_database)
    assert _cors_headers(app, "https://jobs.example.com") == "https://jobs.example.com"
