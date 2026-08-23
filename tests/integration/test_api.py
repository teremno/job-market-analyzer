import hashlib
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from job_market_analyzer.api import create_app
from job_market_analyzer.api import dependencies as api_dependencies
from job_market_analyzer.api.dependencies import (
    DatabaseConfigurationError,
    get_database_session,
)
from job_market_analyzer.intelligence.roles import ROLE_TAXONOMY_VERSION
from job_market_analyzer.intelligence.skills import SKILL_TAXONOMY_VERSION
from job_market_analyzer.models import NormalizedJobPosting, RawJob
from job_market_analyzer.services.geography_analysis import analyze_job_geography
from job_market_analyzer.services.role_analysis import analyze_job_roles
from job_market_analyzer.services.salary_analysis import analyze_job_salary
from job_market_analyzer.services.seniority_analysis import analyze_job_seniority
from job_market_analyzer.services.skill_analysis import analyze_job_skills
from job_market_analyzer.storage.sqlite import connect_database, initialize_database
from job_market_analyzer.storage.sqlite_intelligence_repository import (
    SQLiteGeographyIntelligenceRepository,
    SQLiteRoleIntelligenceRepository,
    SQLiteSalaryIntelligenceRepository,
    SQLiteSeniorityIntelligenceRepository,
    SQLiteSkillIntelligenceRepository,
)
from job_market_analyzer.storage.sqlite_repository import SQLiteJobRepository

BASE_TIME = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
FROZEN_NOW = BASE_TIME + timedelta(days=14)


def _frozen_app(database_path: Path):
    app = create_app(database_path)
    app.state.analytics_now_provider = lambda: FROZEN_NOW
    return app


@pytest.fixture
def api_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "api.sqlite3"
    with closing(connect_database(database_path)) as connection:
        initialize_database(connection)
        jobs = SQLiteJobRepository(connection)
        posting_ids = (
            _persist(
                jobs,
                source="remote_ok",
                external_id="1",
                title="Backend Engineer",
                company="Alpha Labs",
                description="Build Python services with Docker.",
                tags=("Python",),
                published_at=BASE_TIME + timedelta(days=3),
            ),
            _persist(
                jobs,
                source="remote_ok",
                external_id="2",
                title="Backend Engineer",
                company="Beta Labs",
                description="Build Go services with Docker.",
                tags=("Docker", "Go"),
                published_at=BASE_TIME + timedelta(days=2),
            ),
            _persist(
                jobs,
                source="jobicy",
                external_id="3",
                title="Product Manager",
                company="Gamma Products",
                description="Own product outcomes.",
                tags=(),
                published_at=BASE_TIME + timedelta(days=1),
            ),
        )
        _persist(
            jobs,
            source="jobicy",
            external_id="4",
            title="Office Coordinator",
            company="Percent % Company",
            description="Coordinate schedules.",
            tags=(),
            published_at=None,
        )
        postings = {item.id: item for item in jobs.list_job_postings(limit=100)}
        role_repository = SQLiteRoleIntelligenceRepository(connection)
        skill_repository = SQLiteSkillIntelligenceRepository(connection)
        for posting_id in posting_ids:
            analyze_job_roles(postings[posting_id], role_repository)
            analyze_job_skills(postings[posting_id], skill_repository)
    return database_path


@pytest.fixture
def api_client(api_database: Path) -> TestClient:
    with TestClient(_frozen_app(api_database)) as client:
        yield client


def test_startup_requires_existing_current_schema_database(tmp_path: Path) -> None:
    missing = tmp_path / "private-missing.sqlite3"
    with pytest.raises(DatabaseConfigurationError, match="Existing readable SQLite"):
        create_app(missing)
    assert not missing.exists()

    malformed = tmp_path / "private-malformed.sqlite3"
    sqlite3.connect(malformed).close()
    with pytest.raises(DatabaseConfigurationError) as error:
        create_app(malformed)
    assert str(tmp_path) not in str(error.value)


def test_startup_rejects_legacy_schema_without_migrating(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with closing(connect_database(database_path)) as connection:
        connection.executescript(
            """
            CREATE TABLE marker (id INTEGER PRIMARY KEY);
            PRAGMA user_version = 2;
            """
        )
    before = database_path.read_bytes()

    with pytest.raises(DatabaseConfigurationError, match="version 6 is required"):
        create_app(database_path)

    assert database_path.read_bytes() == before


def test_health_openapi_request_id_and_local_cors(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "schema_version": 6}
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["x-request-id"]
    assert api_client.get("/openapi.json").status_code == 200
    assert api_client.get("/docs").status_code == 200


def test_cors_does_not_allow_unlisted_origins(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert "access-control-allow-origin" not in response.headers

    preflight = api_client.options(
        "/api/jobs",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == (
        "http://127.0.0.1:3000"
    )
    assert preflight.headers["x-request-id"]


def test_unknown_route_and_wrong_method_use_stable_errors(api_client: TestClient) -> None:
    missing = api_client.get("/api/not-real")
    wrong_method = api_client.post("/api/health")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"
    assert missing.headers["x-request-id"]
    assert wrong_method.headers["x-request-id"]


def test_jobs_include_stale_parameter_expands_results(
    api_database: Path,
) -> None:
    with closing(connect_database(api_database)) as connection:
        jobs = SQLiteJobRepository(connection)
        _persist(
            jobs,
            source="remote_ok",
            external_id="ancient",
            title="Legacy Perl Engineer",
            company="Old Corp",
            description="Maintain legacy systems.",
            tags=(),
            published_at=BASE_TIME - timedelta(days=45),
            fetched_at=BASE_TIME - timedelta(days=40),
        )

    app = _frozen_app(api_database)
    with TestClient(app) as client:
        active = client.get("/api/jobs", params={"limit": 100})
        with_stale = client.get(
            "/api/jobs",
            params={"limit": 100, "include_stale": "true"},
        )
        stale_only_search = client.get(
            "/api/jobs",
            params={"q": "Legacy Perl", "include_stale": "true"},
        )
        hidden_by_default = client.get("/api/jobs", params={"q": "Legacy Perl"})

    assert active.status_code == 200
    assert with_stale.status_code == 200
    active_count = active.json()["total"]
    stale_count = with_stale.json()["total"]
    assert stale_count == active_count + 1
    assert any(
        item["title"] == "Legacy Perl Engineer" for item in with_stale.json()["items"]
    )
    assert all(
        item["title"] != "Legacy Perl Engineer" for item in active.json()["items"]
    )
    assert stale_only_search.json()["total"] == 1
    assert hidden_by_default.json()["total"] == 0


def test_overview_preserves_posting_level_analytics(api_client: TestClient) -> None:
    response = api_client.get("/api/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["posting_count"] == 4
    assert body["source_count"] == 2
    assert body["role_analysis"] == {
        "not_analyzed": 1,
        "analyzed_zero": 0,
        "analyzed_with_results": 3,
    }
    assert body["skill_analysis"] == {
        "not_analyzed": 1,
        "analyzed_zero": 1,
        "analyzed_with_results": 2,
    }
    assert body["postings_by_source"] == [
        {"source_provider": "jobicy", "posting_count": 2},
        {"source_provider": "remote_ok", "posting_count": 2},
    ]
    assert body["top_roles"][0] == {
        "role_code": "backend",
        "role_name": "Backend",
        "posting_count": 2,
    }


def test_overview_accepts_bounded_top_limit_for_frontend_filter_options(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/overview", params={"top_limit": 100})

    assert response.status_code == 200
    assert len(response.json()["top_roles"]) == 2
    assert len(response.json()["top_skills"]) == 3
    limited = api_client.get("/api/overview", params={"top_limit": 1})
    assert len(limited.json()["top_roles"]) == 1
    assert len(limited.json()["top_skills"]) == 1
    assert api_client.get("/api/overview", params={"top_limit": 0}).status_code == 422
    assert api_client.get("/api/overview", params={"top_limit": 101}).status_code == 422


def test_jobs_pagination_and_bounded_projection(api_client: TestClient) -> None:
    first = api_client.get("/api/jobs", params={"limit": 2})
    second = api_client.get("/api/jobs", params={"limit": 2, "offset": 2})

    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == second.json()["total"] == 4
    assert first.json()["limit"] == 2
    assert first.json()["offset"] == 0
    first_ids = {item["job_posting_id"] for item in first.json()["items"]}
    second_ids = {item["job_posting_id"] for item in second.json()["items"]}
    assert first_ids.isdisjoint(second_ids)
    assert first.json()["items"][0]["title"] == "Backend Engineer"
    serialized = first.text.lower()
    assert "description" not in serialized
    assert "payload" not in serialized


def test_jobs_filters_and_literal_search_are_composable(api_client: TestClient) -> None:
    assert api_client.get("/api/jobs", params={"source": "jobicy"}).json()["total"] == 2
    assert api_client.get("/api/jobs", params={"role": "backend"}).json()["total"] == 2
    assert api_client.get("/api/jobs", params={"skill": "docker"}).json()["total"] == 2
    combined = api_client.get(
        "/api/jobs",
        params={"role": "backend", "skill": "python", "q": "alpha LABS"},
    )
    assert combined.status_code == 200
    assert combined.json()["total"] == 1
    assert combined.json()["items"][0]["company_name"] == "Alpha Labs"
    assert api_client.get("/api/jobs", params={"q": "%"}).json()["total"] == 1
    assert api_client.get(
        "/api/jobs", params={"q": "%' OR 1=1 --"}
    ).json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    (
        {"limit": 0},
        {"limit": 101},
        {"limit": "1.5"},
        {"offset": -1},
        {"offset": 1_000_001},
        {"q": "x" * 201},
        {"source": "x" * 101},
        {"q": "   "},
    ),
)
def test_jobs_reject_invalid_query_parameters(
    api_client: TestClient,
    params: dict[str, int | str],
) -> None:
    response = api_client.get("/api/jobs", params=params)

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_request",
        "message": "Request parameters are invalid.",
    }
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert str(params) not in response.text


def test_role_endpoint_distinguishes_unknown_and_known_zero(
    api_client: TestClient,
) -> None:
    backend = api_client.get("/api/roles/backend")
    zero = api_client.get("/api/roles/design")
    unknown = api_client.get("/api/roles/not-a-role")

    assert backend.status_code == zero.status_code == 200
    assert backend.json()["posting_count"] == 2
    assert backend.json()["top_skills"][0]["skill_code"] == "docker"
    assert zero.json()["posting_count"] == 0
    assert zero.json()["representative_postings"] == []
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "unknown_role"


def test_skill_endpoint_serializes_roles_cooccurrence_and_zero(
    api_client: TestClient,
) -> None:
    docker = api_client.get("/api/skills/docker")
    zero = api_client.get("/api/skills/rust")
    unknown = api_client.get("/api/skills/not-a-skill")

    assert docker.status_code == zero.status_code == 200
    assert docker.json()["posting_count"] == 2
    assert docker.json()["associated_roles"] == [
        {"role_code": "backend", "role_name": "Backend", "posting_count": 2}
    ]
    assert docker.json()["co_occurring_skills"] == [
        {"skill_code": "go", "skill_name": "Go", "posting_count": 1},
        {"skill_code": "python", "skill_name": "Python", "posting_count": 1},
    ]
    assert zero.json()["posting_count"] == 0
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "unknown_skill"


def test_sources_are_deterministic_dataset_summaries(api_client: TestClient) -> None:
    response = api_client.get("/api/sources")

    assert response.status_code == 200
    body = response.json()
    assert [item["source_provider"] for item in body] == ["jobicy", "remote_ok"]
    assert body[0]["role_analysis"] == {
        "not_analyzed": 1,
        "analyzed_zero": 0,
        "analyzed_with_results": 1,
        "with_results_percentage": 50.0,
    }
    assert body[0]["skill_analysis"] == {
        "not_analyzed": 1,
        "analyzed_zero": 1,
        "analyzed_with_results": 0,
        "with_results_percentage": 0.0,
    }
    assert "uptime" not in response.text
    assert "availability" not in response.text


def test_api_requests_do_not_mutate_database(api_database: Path) -> None:
    before = hashlib.sha256(api_database.read_bytes()).digest()
    with TestClient(_frozen_app(api_database)) as client:
        for url in (
            "/api/health",
            "/api/overview",
            "/api/jobs?limit=3&role=backend&skill=docker",
            "/api/roles/backend",
            "/api/skills/docker",
            "/api/sources",
        ):
            assert client.get(url).status_code == 200

    assert hashlib.sha256(api_database.read_bytes()).digest() == before
    with closing(connect_database(api_database)) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_repeated_requests_close_each_connection(
    api_database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(api_database)
    real_connect = api_dependencies.connect_read_only_database
    connections: list[TrackingConnection] = []

    def tracked_connect(database_path: Path) -> TrackingConnection:
        connection = TrackingConnection(real_connect(database_path))
        connections.append(connection)
        return connection

    monkeypatch.setattr(api_dependencies, "connect_read_only_database", tracked_connect)
    with TestClient(app) as client:
        for _ in range(20):
            assert client.get("/api/health").status_code == 200

    assert len(connections) == 20
    assert all(connection.closed for connection in connections)


def test_runtime_database_failure_is_generic_and_path_safe(api_database: Path) -> None:
    app = create_app(api_database)
    api_database.unlink()

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/overview")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert str(api_database) not in response.text
    assert "sqlite" not in response.text.lower()


def test_unexpected_failure_is_generic_and_does_not_leak_internals(
    api_database: Path,
) -> None:
    app = create_app(api_database)

    def fail_dependency() -> None:
        raise RuntimeError("SECRET SQL path C:/private/jobs.sqlite3")

    app.dependency_overrides[get_database_session] = fail_dependency
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/overview")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "SECRET" not in response.text
    assert "C:/private" not in response.text
    assert "SQL" not in response.text


def test_jobs_intelligence_filters_and_salary_fields(api_database: Path) -> None:
    with closing(connect_database(api_database)) as connection:
        jobs = SQLiteJobRepository(connection)
        senior_id = _persist(
            jobs,
            source="remote_ok",
            external_id="senior-paid",
            title="Senior Python Developer",
            company="Paid Corp",
            description="Build services. This is a fully remote position.",
            tags=("Python",),
            published_at=BASE_TIME + timedelta(days=5),
            salary_text="$120k - $150k a year",
        )
        postings = {item.id: item for item in jobs.list_job_postings(limit=100)}
        role_repository = SQLiteRoleIntelligenceRepository(connection)
        skill_repository = SQLiteSkillIntelligenceRepository(connection)
        seniority_repository = SQLiteSeniorityIntelligenceRepository(connection)
        salary_repository = SQLiteSalaryIntelligenceRepository(connection)
        posting = postings[senior_id]
        analyze_job_roles(posting, role_repository)
        analyze_job_skills(posting, skill_repository)
        analyze_job_seniority(posting, seniority_repository)
        analyze_job_salary(posting, salary_repository)
        analyze_job_geography(posting, SQLiteGeographyIntelligenceRepository(connection))

    app = _frozen_app(api_database)
    with TestClient(app) as client:
        by_seniority = client.get(
            "/api/jobs", params={"seniority": "senior", "limit": 100}
        )
        assert by_seniority.status_code == 200
        items = by_seniority.json()["items"]
        assert any(item["title"] == "Senior Python Developer" for item in items)

        remote_only = client.get(
            "/api/jobs",
            params={"geography": "arrangement_remote", "limit": 100},
        )
        assert remote_only.status_code == 200
        assert any(
            item["title"] == "Senior Python Developer"
            and any(
                region["code"] == "region_worldwide" for region in item["regions"]
            )
            for item in remote_only.json()["items"]
        )

        paid = client.get("/api/jobs", params={"has_salary": "true", "limit": 100})
        assert paid.status_code == 200
        paid_items = [
            item
            for item in paid.json()["items"]
            if item["title"] == "Senior Python Developer"
        ]
        assert len(paid_items) == 1
        assert paid_items[0]["salary_currency"] == "USD"
        assert paid_items[0]["salary_annual_min"] == "120000"
        assert paid_items[0]["salary_annual_max"] == "150000"
        assert paid_items[0]["seniority"]["code"] == "senior"

        overview = client.get("/api/overview").json()
        assert overview["salary_posting_count"] >= 1
        assert any(
            item["term_code"] == "senior" for item in overview["top_seniority"]
        )


class TrackingConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.closed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def close(self) -> None:
        self.closed = True
        self._connection.close()


def _persist(
    repository: SQLiteJobRepository,
    *,
    source: str,
    external_id: str,
    title: str,
    company: str,
    description: str,
    tags: tuple[str, ...],
    published_at: datetime | None,
    fetched_at: datetime | None = None,
    salary_text: str | None = None,
):
    source_url = f"https://example.test/{source}/{external_id}"
    result = repository.persist_observation(
        RawJob(
            source_provider=source,
            source_scope="global",
            external_id=external_id,
            source_url=source_url,
            fetched_at=fetched_at or BASE_TIME + timedelta(days=4),
            payload={
                "external_id": external_id,
                "RAW_PAYLOAD_SECRET": "must-not-leak",
            },
        ),
        NormalizedJobPosting(
            source_provider=source,
            source_scope="global",
            external_id=external_id,
            source_url=source_url,
            application_url=f"https://apply.example.test/{external_id}",
            title=title,
            company_name=company,
            description_text=description,
            source_tags=tags,
            location_text="Worldwide",
            published_at=published_at,
            salary_text=salary_text,
        ),
    )
    return result.job_posting_id


def test_fixture_tracks_active_analyzer_contract() -> None:
    assert ROLE_TAXONOMY_VERSION == "2"
    assert SKILL_TAXONOMY_VERSION == "2"


def test_skill_gap_endpoint_computes_and_validates(api_database: Path) -> None:
    app = _frozen_app(api_database)
    with TestClient(app) as client:
        known = client.get(
            "/api/skill-gap",
            params={"role": "backend", "skills": "python,Docker,zzz-unknown"},
        )
        assert known.status_code == 200
        payload = known.json()
        assert payload["role_code"] == "backend"
        assert set(payload["known_recognized"]) >= {"python", "docker"}
        assert "zzz-unknown" in payload["unknown_inputs"]
        for entry in payload["gaps"] + payload["matched_market_skills"]:
            assert entry["status"] in {"gap", "known"}
            assert 0 <= entry["share_of_role_postings"] <= 1

        unknown = client.get("/api/skill-gap", params={"role": "not-a-role"})
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "unknown_role"
