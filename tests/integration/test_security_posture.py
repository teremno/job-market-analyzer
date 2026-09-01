from contextlib import closing
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from job_market_analyzer.api import create_app
from job_market_analyzer.api.rate_limit import (
    RATE_LIMIT_ENV,
    configured_rate_limit,
)
from job_market_analyzer.storage.sqlite import connect_database, initialize_database


@pytest.fixture
def initialized_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "security.sqlite3"
    with closing(connect_database(database_path)) as connection:
        initialize_database(connection)
    return database_path


def test_public_api_surface_is_get_only(initialized_database: Path) -> None:
    app = create_app(initialized_database)

    mutating = [
        (route.path, sorted(route.methods))
        for route in app.routes
        if isinstance(route, APIRoute) and not route.methods <= {"GET", "HEAD"}
    ]

    assert mutating == []


def test_configured_rate_limit_resolution() -> None:
    assert configured_rate_limit({}) == 120
    assert configured_rate_limit({RATE_LIMIT_ENV: "30"}) == 30
    # Explicit zero is the only supported way to disable the limiter.
    assert configured_rate_limit({RATE_LIMIT_ENV: "0"}) is None
    with pytest.raises(ValueError, match=RATE_LIMIT_ENV):
        configured_rate_limit({RATE_LIMIT_ENV: "-5"})
    with pytest.raises(ValueError, match=RATE_LIMIT_ENV):
        configured_rate_limit({RATE_LIMIT_ENV: "many"})


def test_invalid_rate_limit_prevents_unsafe_startup(
    monkeypatch: pytest.MonkeyPatch,
    initialized_database: Path,
) -> None:
    monkeypatch.setenv(RATE_LIMIT_ENV, "invalid")

    with pytest.raises(ValueError, match=RATE_LIMIT_ENV):
        create_app(initialized_database)


@pytest.fixture
def limited_client(
    monkeypatch: pytest.MonkeyPatch,
    initialized_database: Path,
) -> TestClient:
    monkeypatch.setenv(RATE_LIMIT_ENV, "2")
    with TestClient(create_app(initialized_database)) as client:
        yield client


def _get(client: TestClient, path: str, ip: str = "203.0.113.10"):
    return client.get(path, headers={"X-Forwarded-For": ip})


def test_requests_over_limit_receive_429_with_retry_after(
    limited_client: TestClient,
) -> None:
    first = _get(limited_client, "/api/overview")
    second = _get(limited_client, "/api/overview")
    third = _get(limited_client, "/api/overview")

    assert first.status_code == second.status_code == 200
    assert third.status_code == 429
    body = third.json()
    assert body["error"]["code"] == "rate_limited"
    assert int(third.headers["retry-after"]) >= 1
    assert third.headers["x-request-id"] == body["request_id"]
    UUID(body["request_id"])


def test_rate_limit_response_preserves_cors_and_is_not_cacheable(
    limited_client: TestClient,
) -> None:
    headers = {
        "X-Forwarded-For": "203.0.113.11",
        "Origin": "http://localhost:3000",
    }
    assert limited_client.get("/api/overview", headers=headers).status_code == 200
    assert limited_client.get("/api/overview", headers=headers).status_code == 200

    response = limited_client.get("/api/overview", headers=headers)

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    assert response.headers["cache-control"] == "no-store"


def test_health_endpoint_is_exempt_from_rate_limiting(
    limited_client: TestClient,
) -> None:
    for _ in range(10):
        response = _get(limited_client, "/api/health")
        assert response.status_code == 200


def test_buckets_are_independent_per_client_ip(
    limited_client: TestClient,
) -> None:
    assert _get(limited_client, "/api/overview").status_code == 200
    assert _get(limited_client, "/api/overview").status_code == 200
    assert _get(limited_client, "/api/overview", ip="198.51.100.77").status_code == 200


def test_zero_limit_disables_rate_limiting(
    monkeypatch: pytest.MonkeyPatch,
    initialized_database: Path,
) -> None:
    monkeypatch.setenv(RATE_LIMIT_ENV, "0")
    with TestClient(create_app(initialized_database)) as client:
        for _ in range(8):
            response = client.get("/api/overview")
            assert response.status_code == 200
