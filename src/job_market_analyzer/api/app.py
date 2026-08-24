"""FastAPI application factory for the local read-only Dashboard v0 API."""

import logging
import os
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Path as ApiPath, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AfterValidator
from starlette.exceptions import HTTPException as StarletteHTTPException

from job_market_analyzer.analytics import PostingSearchFilters
from job_market_analyzer.api.dependencies import (
    ApiDatabaseSession,
    DatabaseUnavailableError,
    get_database_session,
    validate_database_path,
)
from job_market_analyzer.api.models import (
    AnalyticsOverviewResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    JobsResponse,
    MarketSkillResponse,
    RoleDetailResponse,
    SkillDetailResponse,
    SkillGapResponse,
    SourceSummaryResponse,
)
from job_market_analyzer.services.skill_gap import compute_skill_gap
from job_market_analyzer.storage.sqlite import CURRENT_SCHEMA_VERSION


def _strip_non_blank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


LOGGER = logging.getLogger(__name__)
LOCAL_DASHBOARD_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _configured_cors_origins() -> list[str]:
    """Resolve CORS origins: env override first, localhost defaults second.

    ``JMA_CORS_ORIGINS`` accepts a comma-separated list of exact origins for
    public deployments (for example ``https://example.com``). Unparseable or
    wildcard values are ignored so the safe local default can never be
    silently widened into ``*``.
    """

    raw = os.getenv("JMA_CORS_ORIGINS", "").strip()
    if not raw:
        return list(LOCAL_DASHBOARD_ORIGINS)
    origins: list[str] = []
    for candidate in raw.split(","):
        origin = candidate.strip().rstrip("/")
        valid = origin.startswith("http://") or origin.startswith("https://")
        if valid and origin not in origins:
            origins.append(origin)
        if not valid:
            LOGGER.warning(
                "Ignoring invalid JMA_CORS_ORIGINS entry: %r", candidate
            )
    if not origins:
        LOGGER.warning(
            "JMA_CORS_ORIGINS was set but produced no valid origins; "
            "falling back to localhost defaults."
        )
    return origins or list(LOCAL_DASHBOARD_ORIGINS)

DatabaseSession = Annotated[ApiDatabaseSession, Depends(get_database_session)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]
TopLimit = Annotated[int, Query(ge=1, le=100)]
NonBlankString = Annotated[str, AfterValidator(_strip_non_blank)]
SourceFilter = Annotated[
    NonBlankString | None,
    Query(alias="source", min_length=1, max_length=100),
]
RoleFilter = Annotated[
    NonBlankString | None,
    Query(alias="role", min_length=1, max_length=100),
]
SkillFilter = Annotated[
    NonBlankString | None,
    Query(alias="skill", min_length=1, max_length=100),
]
SearchFilter = Annotated[
    NonBlankString | None,
    Query(alias="q", min_length=1, max_length=200),
]
CodePath = Annotated[NonBlankString, ApiPath(min_length=1, max_length=100)]


class ApiNotFoundError(RuntimeError):
    """A requested active taxonomy code is unknown."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message


def create_app(database_path: Path) -> FastAPI:
    """Create a local API bound to one validated existing SQLite database."""

    resolved_path = validate_database_path(database_path)
    app = FastAPI(
        title="Job Market Analyzer Local API",
        version="0.1.0",
        description="Read-only posting-level API for Dashboard v0.",
    )
    app.state.database_path = resolved_path

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_configured_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=[],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = uuid4()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = str(request_id)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="invalid_request",
            message="Request parameters are invalid.",
        )

    @app.exception_handler(ApiNotFoundError)
    async def not_found_handler(
        request: Request,
        exc: ApiNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            code=exc.code,
            message=exc.public_message,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            code, message = "not_found", "The requested endpoint was not found."
        elif exc.status_code == 405:
            code, message = "method_not_allowed", "The HTTP method is not allowed."
        else:
            code, message = "http_error", "The HTTP request could not be completed."
        return _error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(DatabaseUnavailableError)
    async def database_error_handler(
        request: Request,
        exc: DatabaseUnavailableError,
    ) -> JSONResponse:
        LOGGER.exception(
            "api_database_unavailable request_id=%s path=%s",
            _request_id(request),
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error_response(
            request,
            status_code=503,
            code="database_unavailable",
            message="The analytics database is temporarily unavailable.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        LOGGER.exception(
            "api_request_failed request_id=%s path=%s",
            _request_id(request),
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="The request could not be completed.",
        )

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        summary="Check API and database availability",
    )
    def health(session: DatabaseSession) -> HealthResponse:
        version = session.connection.execute("PRAGMA user_version").fetchone()[0]
        if version != CURRENT_SCHEMA_VERSION:
            raise DatabaseUnavailableError("The analytics database schema changed.")
        session.connection.execute("SELECT 1 FROM job_postings LIMIT 1").fetchone()
        return HealthResponse(status="ok", schema_version=version)

    @app.get(
        "/api/overview",
        response_model=AnalyticsOverviewResponse,
        summary="Get posting-level market overview",
    )
    def overview(
        session: DatabaseSession,
        top_limit: TopLimit = 10,
    ) -> AnalyticsOverviewResponse:
        return AnalyticsOverviewResponse.from_dto(
            session.analytics.get_overview(top_limit=top_limit)
        )

    @app.get(
        "/api/jobs",
        response_model=JobsResponse,
        summary="List and filter current source postings",
    )
    def jobs(
        session: DatabaseSession,
        limit: Limit = 50,
        offset: Offset = 0,
        source: SourceFilter = None,
        role: RoleFilter = None,
        skill: SkillFilter = None,
        q: SearchFilter = None,
        include_stale: Annotated[
            bool,
            Query(
                description=(
                    "Include postings no longer observed within the freshness "
                    "window (historical rows are kept, never deleted)."
                )
            ),
        ] = False,
        seniority: Annotated[
            str | None,
            Query(alias="seniority", min_length=1, max_length=100),
        ] = None,
        geography: Annotated[
            str | None,
            Query(
                alias="geography",
                min_length=1,
                max_length=100,
                description=(
                    "Arrangement or region code, for example "
                    "'arrangement_remote' or 'region_worldwide'."
                ),
            ),
        ] = None,
        has_salary: Annotated[
            bool | None, Query(description="Only postings with a salary estimate.")
        ] = None,
    ) -> JobsResponse:
        page = session.analytics.list_postings(
            PostingSearchFilters(
                source_provider=source,
                role_code=role,
                skill_code=skill,
                seniority_code=seniority,
                geography_code=geography,
                has_salary=has_salary,
                search_text=q,
            ),
            limit=limit,
            offset=offset,
            include_stale=include_stale,
        )
        return JobsResponse.from_dto(page)

    @app.get(
        "/api/skill-gap",
        response_model=SkillGapResponse,
        summary="Compute a deterministic read-only skill gap for one role",
    )
    def skill_gap(
        session: DatabaseSession,
        role: RoleFilter,
        skills: Annotated[
            str | None,
            Query(
                alias="skills",
                max_length=500,
                description=(
                    "Comma-separated skills you already have, by code or "
                    "display name."
                ),
            ),
        ] = None,
        top: TopLimit = 15,
    ) -> SkillGapResponse:
        report = compute_skill_gap(
            session.analytics,
            role_code=role,
            known_skill_inputs=(skills or "").split(","),
        )
        if report is None:
            raise ApiNotFoundError("unknown_role", "The role code is not recognized.")
        return SkillGapResponse(
            role_code=report.role_code,
            role_name=report.role_name,
            role_posting_count=report.role_posting_count,
            known_recognized=report.known_recognized,
            unknown_inputs=report.unknown_inputs,
            gaps=tuple(
                MarketSkillResponse(
                    skill_code=item.skill_code,
                    skill_name=item.skill_name,
                    posting_count=item.posting_count,
                    share_of_role_postings=item.share_of_role_postings,
                    status=item.status,
                )
                for item in report.gaps[:top]
            ),
            matched_market_skills=tuple(
                MarketSkillResponse(
                    skill_code=item.skill_code,
                    skill_name=item.skill_name,
                    posting_count=item.posting_count,
                    share_of_role_postings=item.share_of_role_postings,
                    status=item.status,
                )
                for item in report.matched_market_skills[:top]
            ),
        )

    @app.get(
        "/api/roles/{role_code}",
        response_model=RoleDetailResponse,
        summary="Get one active role summary",
    )
    def role_detail(role_code: CodePath, session: DatabaseSession) -> RoleDetailResponse:
        detail = session.analytics.get_role_detail(role_code)
        if detail is None:
            raise ApiNotFoundError("unknown_role", "The role code is not recognized.")
        return RoleDetailResponse.from_dto(detail)

    @app.get(
        "/api/skills/{skill_code}",
        response_model=SkillDetailResponse,
        summary="Get one active skill summary",
    )
    def skill_detail(skill_code: CodePath, session: DatabaseSession) -> SkillDetailResponse:
        detail = session.analytics.get_skill_detail(skill_code)
        if detail is None:
            raise ApiNotFoundError("unknown_skill", "The skill code is not recognized.")
        return SkillDetailResponse.from_dto(detail)

    @app.get(
        "/api/sources",
        response_model=tuple[SourceSummaryResponse, ...],
        summary="Get observed source dataset summaries",
    )
    def sources(session: DatabaseSession) -> tuple[SourceSummaryResponse, ...]:
        return tuple(
            SourceSummaryResponse.from_dto(item)
            for item in session.analytics.list_source_summaries()
        )

    return app


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message),
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _request_id(request: Request) -> UUID:
    return getattr(request.state, "request_id", uuid4())
