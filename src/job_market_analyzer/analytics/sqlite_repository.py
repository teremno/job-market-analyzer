"""SQLite implementation of the read-only posting-level analytics contract."""

import json
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from uuid import UUID

from job_market_analyzer.analytics.models import (
    AnalysisStatus,
    AnalyticsOverview,
    NamedRole,
    NamedSkill,
    NamedTerm,
    PagedPostings,
    PostingListItem,
    PostingSearchFilters,
    RoleCount,
    RoleDetail,
    SalaryCurrencySummary,
    SkillCount,
    SkillDetail,
    SourcePostingCount,
    SourceSummary,
    TermCount,
)
from job_market_analyzer.intelligence.geography import (
    GEOGRAPHY_TERMS,
    GEOGRAPHY_TAXONOMY_VERSION,
)
from job_market_analyzer.intelligence.hashing import (
    calculate_geography_input_hash,
    calculate_role_input_hash,
    calculate_salary_input_hash,
    calculate_seniority_input_hash,
    calculate_skill_input_hash,
)
from job_market_analyzer.intelligence.repository import (
    GEOGRAPHY_ANALYZER_KIND,
    ROLE_ANALYZER_KIND,
    SALARY_ANALYZER_KIND,
    SENIORITY_ANALYZER_KIND,
    SKILL_ANALYZER_KIND,
)
from job_market_analyzer.intelligence.roles import (
    ROLE_TAXONOMY,
    ROLE_TAXONOMY_VERSION,
)
from job_market_analyzer.intelligence.salaries import SALARY_TAXONOMY_VERSION
from job_market_analyzer.intelligence.seniority import (
    SENIORITY_TAXONOMY,
    SENIORITY_TAXONOMY_VERSION,
)
from job_market_analyzer.intelligence.skills import (
    SKILL_TAXONOMY,
    SKILL_TAXONOMY_VERSION,
)
from job_market_analyzer.storage.serialization import (
    deserialize_source_tags,
    serialize_utc_datetime,
)

MAX_PAGE_SIZE = 100
MAX_AGGREGATE_LIMIT = 100
ACTIVE_POSTING_WINDOW_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(UTC)

_ROLE_NAMES = {role.code: role.name for role in ROLE_TAXONOMY}
_SKILL_NAMES = {skill.code: skill.name for skill in SKILL_TAXONOMY}
_SENIORITY_NAMES = {level.code: level.name for level in SENIORITY_TAXONOMY}
_GEOGRAPHY_NAMES = {term.code: term.name for term in GEOGRAPHY_TERMS}

_ACTIVE_POSTINGS_CTE = """
active_postings AS (
    SELECT job_postings.id,
           job_postings.title,
           job_postings.description_text,
           job_postings.source_tags_json,
           job_postings.location_text,
           job_postings.is_remote,
           job_postings.salary_text,
           job_postings.salary_min,
           job_postings.salary_max,
           job_postings.salary_currency,
           job_postings.salary_period
    FROM job_postings
    WHERE job_postings.last_seen_at >= ?
)
"""

_KIND_RUN_CTES: dict[str, str] = {
    ROLE_ANALYZER_KIND: """
current_role_runs AS (
    SELECT analysis_runs.id, analysis_runs.job_posting_id
    FROM analysis_runs
    JOIN active_postings
      ON active_postings.id = analysis_runs.job_posting_id
    WHERE analysis_runs.analyzer_kind = ?
      AND analysis_runs.taxonomy_version = ?
      AND analysis_runs.extractor_version = ?
      AND analysis_runs.input_hash = jma_role_input_hash(
          active_postings.title,
          active_postings.description_text
      )
)""",
    SKILL_ANALYZER_KIND: """
current_skill_runs AS (
    SELECT analysis_runs.id, analysis_runs.job_posting_id
    FROM analysis_runs
    JOIN active_postings
      ON active_postings.id = analysis_runs.job_posting_id
    WHERE analysis_runs.analyzer_kind = ?
      AND analysis_runs.taxonomy_version = ?
      AND analysis_runs.extractor_version = ?
      AND analysis_runs.input_hash = jma_skill_input_hash(
          active_postings.title,
          active_postings.description_text,
          active_postings.source_tags_json
      )
)""",
    SENIORITY_ANALYZER_KIND: """
current_seniority_runs AS (
    SELECT analysis_runs.id, analysis_runs.job_posting_id
    FROM analysis_runs
    JOIN active_postings
      ON active_postings.id = analysis_runs.job_posting_id
    WHERE analysis_runs.analyzer_kind = ?
      AND analysis_runs.taxonomy_version = ?
      AND analysis_runs.extractor_version = ?
      AND analysis_runs.input_hash = jma_seniority_input_hash(
          active_postings.title
      )
)""",
    GEOGRAPHY_ANALYZER_KIND: """
current_geography_runs AS (
    SELECT analysis_runs.id, analysis_runs.job_posting_id
    FROM analysis_runs
    JOIN active_postings
      ON active_postings.id = analysis_runs.job_posting_id
    WHERE analysis_runs.analyzer_kind = ?
      AND analysis_runs.taxonomy_version = ?
      AND analysis_runs.extractor_version = ?
      AND analysis_runs.input_hash = jma_geography_input_hash(
          active_postings.description_text,
          active_postings.location_text,
          active_postings.is_remote
      )
)""",
    SALARY_ANALYZER_KIND: """
current_salary_runs AS (
    SELECT analysis_runs.id, analysis_runs.job_posting_id
    FROM analysis_runs
    JOIN active_postings
      ON active_postings.id = analysis_runs.job_posting_id
    WHERE analysis_runs.analyzer_kind = ?
      AND analysis_runs.taxonomy_version = ?
      AND analysis_runs.extractor_version = ?
      AND analysis_runs.input_hash = jma_salary_input_hash(
          active_postings.salary_text,
          active_postings.salary_min,
          active_postings.salary_max,
          active_postings.salary_currency,
          active_postings.salary_period
      )
)""",
}


def _runs_ctes(*analyzer_kinds: str) -> tuple[str, tuple[str, ...]]:
    """Compose exact-current run CTEs for only the requested analyzer kinds.

    Each excluded kind skips its expensive Python-UDF input-hash evaluation,
    so narrow queries stay proportional to the hashes they actually need.
    """

    kind_versions = {
        ROLE_ANALYZER_KIND: ROLE_TAXONOMY_VERSION,
        SKILL_ANALYZER_KIND: SKILL_TAXONOMY_VERSION,
        SENIORITY_ANALYZER_KIND: SENIORITY_TAXONOMY_VERSION,
        GEOGRAPHY_ANALYZER_KIND: GEOGRAPHY_TAXONOMY_VERSION,
        SALARY_ANALYZER_KIND: SALARY_TAXONOMY_VERSION,
    }
    ordered_kinds = [
        kind for kind in _KIND_RUN_CTES if kind in analyzer_kinds
    ]
    if not ordered_kinds:
        raise ValueError("at least one analyzer kind is required")
    ctes = ",\n".join(_KIND_RUN_CTES[kind] for kind in ordered_kinds)
    parameters: tuple[str, ...] = ()
    for kind in ordered_kinds:
        version = kind_versions[kind]
        parameters = (*parameters, kind, version, version)
    return f"WITH {_ACTIVE_POSTINGS_CTE}, {ctes}", parameters


class SQLiteAnalyticsRepository:
    """Execute bounded, parameterized analytics using a caller-owned connection."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if connection.row_factory is not sqlite3.Row:
            raise ValueError(
                "SQLiteAnalyticsRepository requires connection.row_factory to be "
                "sqlite3.Row; create the connection with connect_database()"
            )
        self._connection = connection
        self._now_provider = now_provider if now_provider is not None else _utc_now
        connection.create_function(
            "jma_role_input_hash",
            2,
            calculate_role_input_hash,
            deterministic=True,
        )
        connection.create_function(
            "jma_skill_input_hash",
            3,
            _calculate_persisted_skill_input_hash,
            deterministic=True,
        )
        connection.create_function(
            "jma_seniority_input_hash",
            1,
            _calculate_persisted_seniority_input_hash,
            deterministic=True,
        )
        connection.create_function(
            "jma_geography_input_hash",
            3,
            _calculate_persisted_geography_input_hash,
            deterministic=True,
        )
        connection.create_function(
            "jma_salary_input_hash",
            5,
            _calculate_persisted_salary_input_hash,
            deterministic=True,
        )

    def _active_cutoff(self) -> str:
        """Return the serialized cutoff separating active from stale postings."""

        cutoff = self._now_provider() - timedelta(days=ACTIVE_POSTING_WINDOW_DAYS)
        return serialize_utc_datetime(cutoff)

    def _top_seniority_counts(self, limit: int) -> tuple[TermCount, ...]:
        ctes, parameters = _runs_ctes(SENIORITY_ANALYZER_KIND)
        rows = self._connection.execute(
            ctes
            + """
            , seniority_counts AS (
                SELECT job_seniority.seniority_code AS code,
                       COUNT(DISTINCT current_seniority_runs.job_posting_id)
                           AS posting_count
                FROM current_seniority_runs
                JOIN job_seniority
                  ON job_seniority.analysis_run_id = current_seniority_runs.id
                GROUP BY 1 ORDER BY 2 DESC LIMIT ?
            )
            SELECT code, posting_count FROM seniority_counts
            """,
            (self._active_cutoff(), *parameters, limit),
        ).fetchall()
        return tuple(
            TermCount(
                term_code=row["code"],
                term_name=_SENIORITY_NAMES.get(row["code"], row["code"]),
                posting_count=row["posting_count"],
            )
            for row in rows
        )

    def _geography_dimension_counts(
        self,
        limit: int,
    ) -> tuple[TermCount, ...]:
        """Return both geography dimensions in one scan, region codes prefixed."""

        ctes, parameters = _runs_ctes(GEOGRAPHY_ANALYZER_KIND)
        rows = self._connection.execute(
            ctes
            + """
            , geography_dimension_counts AS (
                SELECT job_geography.geography_code AS code,
                       gt.dimension AS dimension,
                       COUNT(DISTINCT current_geography_runs.job_posting_id)
                           AS posting_count
                FROM current_geography_runs
                JOIN job_geography
                  ON job_geography.analysis_run_id = current_geography_runs.id
                JOIN geography_terms gt ON gt.code = job_geography.geography_code
                GROUP BY 1 ORDER BY 3 DESC, 1 ASC LIMIT ?
            )
            SELECT code, dimension, posting_count FROM geography_dimension_counts
            """,
            (self._active_cutoff(), *parameters, limit * 2),
        ).fetchall()
        return tuple(
            TermCount(
                term_code=row["code"],
                term_name=_GEOGRAPHY_NAMES.get(row["code"], row["code"]),
                posting_count=row["posting_count"],
            )
            for row in rows
        )

    def _salary_summary(self) -> dict[str, object]:
        ctes, parameters = _runs_ctes(SALARY_ANALYZER_KIND)
        count_row = self._connection.execute(
            ctes
            + """
            SELECT COUNT(DISTINCT current_salary_runs.job_posting_id)
                       AS salary_postings
            FROM current_salary_runs
            JOIN job_salaries
              ON job_salaries.analysis_run_id = current_salary_runs.id
            """,
            (self._active_cutoff(), *parameters),
        ).fetchone()

        # One grouped pass yields per-currency counts and the full annual-minimum
        # distribution; medians are computed in Python from the repeats. No
        # global LIMIT: truncating groups would silently bias medians once the
        # dataset has many distinct values per currency.
        grouped_rows = self._connection.execute(
            ctes
            + """
            , salary_currencies AS (
                SELECT job_salaries.currency AS currency,
                       job_salaries.annual_min AS annual_min,
                       COUNT(DISTINCT current_salary_runs.job_posting_id)
                           AS posting_count
                FROM current_salary_runs
                JOIN job_salaries
                  ON job_salaries.analysis_run_id = current_salary_runs.id
                WHERE job_salaries.currency IS NOT NULL
                  AND job_salaries.annual_min IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1 ASC, 2 ASC
            )
            SELECT currency, annual_min, posting_count FROM salary_currencies
            """,
            (self._active_cutoff(), *parameters),
        ).fetchall()

        postings_by_currency: dict[str, int] = {}
        values_by_currency: dict[str, list[str]] = {}
        for row in grouped_rows:
            currency = row["currency"]
            count = row["posting_count"]
            postings_by_currency[currency] = (
                postings_by_currency.get(currency, 0) + count
            )
            values_by_currency.setdefault(currency, []).extend(
                [row["annual_min"]] * count
            )

        summaries: list[SalaryCurrencySummary] = []
        for currency in sorted(
            postings_by_currency,
            key=lambda item: (-postings_by_currency[item], item),
        )[:MAX_AGGREGATE_LIMIT]:
            values = values_by_currency[currency]
            middle = len(values) // 2
            if not values:
                median = None
            elif len(values) % 2 == 1:
                try:
                    median = _decimal_string(Decimal(values[middle]))
                except (InvalidOperation, ValueError):
                    median = values[middle]
            else:
                try:
                    low = Decimal(values[middle - 1])
                    high = Decimal(values[middle])
                    median = _decimal_string((low + high) / 2)
                except (InvalidOperation, ValueError):
                    median = values[middle - 1]
            summaries.append(
                SalaryCurrencySummary(
                    currency=currency,
                    postings=postings_by_currency[currency],
                    median_annual_min=median,
                )
            )
        return {
            "salary_posting_count": (
                count_row["salary_postings"] if count_row else 0
            ),
            "salary_currencies": tuple(summaries),
        }

    def _active_condition(self, *, include_stale: bool) -> tuple[str, list[str]]:
        if include_stale:
            return "1 = 1", []
        return "job_postings.last_seen_at >= ?", [self._active_cutoff()]

    def get_overview(self, *, top_limit: int = 10) -> AnalyticsOverview:
        """Return current posting-level counts without evidence inflation."""

        _validate_bounded_limit(top_limit, "top_limit", MAX_AGGREGATE_LIMIT)
        overview_ctes, overview_parameters = _runs_ctes(
            ROLE_ANALYZER_KIND, SKILL_ANALYZER_KIND
        )
        row = self._connection.execute(
            overview_ctes
            + """
            , role_evidence_counts AS (
                SELECT analysis_run_id, COUNT(*) AS evidence_count
                FROM job_roles
                GROUP BY analysis_run_id
            ),
            skill_evidence_counts AS (
                SELECT analysis_run_id, COUNT(*) AS evidence_count
                FROM job_skills
                GROUP BY analysis_run_id
            ),
            status AS (
                SELECT
                    COUNT(*) AS posting_count,
                    COUNT(DISTINCT job_postings.source_provider) AS source_count,
                    SUM(CASE WHEN current_role_runs.id IS NOT NULL
                                  AND COALESCE(
                                      role_evidence_counts.evidence_count, 0
                                  ) > 0
                             THEN 1 ELSE 0 END) AS role_classified,
                    SUM(CASE WHEN current_role_runs.id IS NOT NULL
                                  AND COALESCE(
                                      role_evidence_counts.evidence_count, 0
                                  ) = 0
                             THEN 1 ELSE 0 END) AS role_zero,
                    SUM(CASE WHEN current_role_runs.id IS NULL
                             THEN 1 ELSE 0 END) AS role_not_analyzed,
                    SUM(CASE WHEN current_skill_runs.id IS NOT NULL
                                  AND COALESCE(
                                      skill_evidence_counts.evidence_count, 0
                                  ) > 0
                             THEN 1 ELSE 0 END) AS skill_classified,
                    SUM(CASE WHEN current_skill_runs.id IS NOT NULL
                                  AND COALESCE(
                                      skill_evidence_counts.evidence_count, 0
                                  ) = 0
                             THEN 1 ELSE 0 END) AS skill_zero,
                    SUM(CASE WHEN current_skill_runs.id IS NULL
                             THEN 1 ELSE 0 END) AS skill_not_analyzed
                FROM job_postings
                LEFT JOIN current_role_runs
                  ON current_role_runs.job_posting_id = job_postings.id
                LEFT JOIN role_evidence_counts
                  ON role_evidence_counts.analysis_run_id = current_role_runs.id
                LEFT JOIN current_skill_runs
                  ON current_skill_runs.job_posting_id = job_postings.id
                LEFT JOIN skill_evidence_counts
                  ON skill_evidence_counts.analysis_run_id = current_skill_runs.id
                WHERE job_postings.last_seen_at >= ?
            ),
            source_counts AS (
                SELECT source_provider, COUNT(*) AS posting_count
                FROM job_postings
                WHERE job_postings.last_seen_at >= ?
                GROUP BY source_provider
                ORDER BY posting_count DESC, source_provider ASC
            ),
            role_counts AS (
                SELECT job_roles.role_code,
                       COUNT(DISTINCT current_role_runs.job_posting_id)
                           AS posting_count
                FROM current_role_runs
                JOIN job_roles ON job_roles.analysis_run_id = current_role_runs.id
                GROUP BY job_roles.role_code
                ORDER BY posting_count DESC, job_roles.role_code ASC
                LIMIT ?
            ),
            skill_counts AS (
                SELECT job_skills.skill_code,
                       COUNT(DISTINCT current_skill_runs.job_posting_id)
                           AS posting_count
                FROM current_skill_runs
                JOIN job_skills ON job_skills.analysis_run_id = current_skill_runs.id
                GROUP BY job_skills.skill_code
                ORDER BY posting_count DESC, job_skills.skill_code ASC
                LIMIT ?
            )
            SELECT
                status.*,
                COALESCE((
                    SELECT json_group_array(json_object(
                        'source_provider', source_provider,
                        'posting_count', posting_count
                    ))
                    FROM (
                        SELECT source_provider, posting_count
                        FROM source_counts
                        ORDER BY posting_count DESC, source_provider ASC
                    ) ordered_source_counts
                ), '[]') AS source_counts_json,
                COALESCE((
                    SELECT json_group_array(json_object(
                        'role_code', role_code,
                        'posting_count', posting_count
                    ))
                    FROM (
                        SELECT role_code, posting_count
                        FROM role_counts
                        ORDER BY posting_count DESC, role_code ASC
                    ) ordered_role_counts
                ), '[]') AS role_counts_json,
                COALESCE((
                    SELECT json_group_array(json_object(
                        'skill_code', skill_code,
                        'posting_count', posting_count
                    ))
                    FROM (
                        SELECT skill_code, posting_count
                        FROM skill_counts
                        ORDER BY posting_count DESC, skill_code ASC
                    ) ordered_skill_counts
                ), '[]') AS skill_counts_json
            FROM status
            """,
            (
                self._active_cutoff(),
                *overview_parameters,
                self._active_cutoff(),
                self._active_cutoff(),
                top_limit,
                top_limit,
            ),
        ).fetchone()
        source_rows = json.loads(row["source_counts_json"])
        role_rows = json.loads(row["role_counts_json"])
        skill_rows = json.loads(row["skill_counts_json"])
        return AnalyticsOverview(
            posting_count=row["posting_count"],
            source_count=row["source_count"],
            current_role_classified_posting_count=row["role_classified"] or 0,
            current_role_unknown_posting_count=row["role_zero"] or 0,
            current_role_not_analyzed_posting_count=row["role_not_analyzed"] or 0,
            current_skill_classified_posting_count=row["skill_classified"] or 0,
            current_skill_zero_posting_count=row["skill_zero"] or 0,
            current_skill_not_analyzed_posting_count=(
                row["skill_not_analyzed"] or 0
            ),
            postings_by_source=tuple(
                SourcePostingCount(
                    source_provider=row["source_provider"],
                    posting_count=row["posting_count"],
                )
                for row in source_rows
            ),
            top_roles=tuple(_role_count_dict(item) for item in role_rows),
            top_skills=tuple(_skill_count_dict(item) for item in skill_rows),
            top_seniority=self._top_seniority_counts(top_limit),
            **self._geography_overview_terms(top_limit),
            **self._salary_summary(),
        )

    def _geography_overview_terms(self, limit: int) -> dict[str, object]:
        all_terms = self._geography_dimension_counts(limit)
        return {
            "arrangement_counts": tuple(
                term for term in all_terms if term.term_code.startswith("arrangement_")
            ),
            "region_counts": tuple(
                term for term in all_terms if term.term_code.startswith("region_")
            ),
        }

    def list_postings(
        self,
        filters: PostingSearchFilters = PostingSearchFilters(),
        *,
        limit: int = 50,
        offset: int = 0,
        include_stale: bool = False,
    ) -> PagedPostings:
        """Return a stable page and load role/skill labels in two batch queries.

        By default only active postings (observed within the freshness window)
        are returned; ``include_stale=True`` also returns historical postings.
        """

        _validate_bounded_limit(limit, "limit", MAX_PAGE_SIZE)
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be non-negative")
        where_sql, filter_parameters = _posting_filter_sql(filters)
        active_sql, active_parameters = self._active_condition(
            include_stale=include_stale
        )
        current_parameters = self._current_run_parameters()
        count = self._connection.execute(
            f"""
            SELECT COUNT(*) AS posting_count
            FROM job_postings
            WHERE {where_sql}
              AND {active_sql}
            """,
            (*filter_parameters, *active_parameters),
        ).fetchone()["posting_count"]
        rows = self._connection.execute(
            f"""
            SELECT
                job_postings.id,
                job_postings.canonical_job_id,
                job_postings.source_provider,
                job_postings.source_scope,
                job_postings.external_id,
                job_postings.company_name,
                job_postings.title,
                job_postings.location_text,
                job_postings.published_at,
                job_postings.last_seen_at,
                job_postings.source_url,
                job_postings.application_url,
                role_runs.id AS role_run_id,
                skill_runs.id AS skill_run_id,
                seniority_runs.id AS seniority_run_id,
                geography_runs.id AS geography_run_id,
                salary_runs.id AS salary_run_id
            FROM job_postings
            LEFT JOIN analysis_runs role_runs
              ON role_runs.job_posting_id = job_postings.id
             AND role_runs.analyzer_kind = ?
             AND role_runs.taxonomy_version = ?
             AND role_runs.extractor_version = ?
             AND role_runs.input_hash = jma_role_input_hash(
                 job_postings.title,
                 job_postings.description_text
             )
            LEFT JOIN analysis_runs skill_runs
              ON skill_runs.job_posting_id = job_postings.id
             AND skill_runs.analyzer_kind = ?
             AND skill_runs.taxonomy_version = ?
             AND skill_runs.extractor_version = ?
             AND skill_runs.input_hash = jma_skill_input_hash(
                 job_postings.title,
                 job_postings.description_text,
                 job_postings.source_tags_json
             )
            LEFT JOIN analysis_runs seniority_runs
              ON seniority_runs.job_posting_id = job_postings.id
             AND seniority_runs.analyzer_kind = ?
             AND seniority_runs.taxonomy_version = ?
             AND seniority_runs.extractor_version = ?
             AND seniority_runs.input_hash = jma_seniority_input_hash(
                 job_postings.title
             )
            LEFT JOIN analysis_runs geography_runs
              ON geography_runs.job_posting_id = job_postings.id
             AND geography_runs.analyzer_kind = ?
             AND geography_runs.taxonomy_version = ?
             AND geography_runs.extractor_version = ?
             AND geography_runs.input_hash = jma_geography_input_hash(
                 job_postings.description_text,
                 job_postings.location_text,
                 job_postings.is_remote
             )
            LEFT JOIN analysis_runs salary_runs
              ON salary_runs.job_posting_id = job_postings.id
             AND salary_runs.analyzer_kind = ?
             AND salary_runs.taxonomy_version = ?
             AND salary_runs.extractor_version = ?
             AND salary_runs.input_hash = jma_salary_input_hash(
                 job_postings.salary_text,
                 job_postings.salary_min,
                 job_postings.salary_max,
                 job_postings.salary_currency,
                 job_postings.salary_period
             )
            WHERE {where_sql}
              AND {active_sql}
            ORDER BY
                job_postings.published_at IS NULL ASC,
                job_postings.published_at DESC,
                job_postings.last_seen_at DESC,
                job_postings.source_provider ASC,
                job_postings.source_scope ASC,
                job_postings.external_id ASC,
                job_postings.id ASC
            LIMIT ? OFFSET ?
            """,
            (
                *current_parameters,
                *filter_parameters,
                *active_parameters,
                limit,
                offset,
            ),
        ).fetchall()
        (
            roles_by_posting,
            skills_by_posting,
            seniority_by_posting,
            geography_by_posting,
            salary_by_posting,
            current_role_posting_ids,
            current_skill_posting_ids,
        ) = self._page_intelligence(rows)
        return PagedPostings(
            items=tuple(
                _posting_list_item(
                    row,
                    roles_by_posting.get(row["id"], ()),
                    skills_by_posting.get(row["id"], ()),
                    seniority=seniority_by_posting.get(row["id"]),
                    geography=geography_by_posting.get(row["id"], ()),
                    salary=salary_by_posting.get(row["id"]),
                    role_run_is_current=row["id"] in current_role_posting_ids,
                    skill_run_is_current=row["id"] in current_skill_posting_ids,
                )
                for row in rows
            ),
            posting_count=count,
            limit=limit,
            offset=offset,
        )

    def get_role_detail(
        self,
        role_code: str,
        *,
        top_limit: int = 10,
        posting_limit: int = 5,
    ) -> RoleDetail | None:
        """Return mentioned skills among postings with one current role."""

        _validate_bounded_limit(top_limit, "top_limit", MAX_AGGREGATE_LIMIT)
        _validate_bounded_limit(posting_limit, "posting_limit", MAX_PAGE_SIZE)
        role_name = _ROLE_NAMES.get(role_code)
        if role_name is None:
            return None
        page = self.list_postings(
            PostingSearchFilters(role_code=role_code),
            limit=posting_limit,
        )
        rows = self._connection.execute(
            """
            WITH selected_current_role_runs AS (
                SELECT DISTINCT analysis_runs.id, analysis_runs.job_posting_id
                FROM job_roles selected_role
                JOIN analysis_runs
                  ON analysis_runs.id = selected_role.analysis_run_id
                JOIN job_postings
                  ON job_postings.id = analysis_runs.job_posting_id
                WHERE selected_role.role_code = ?
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                  AND analysis_runs.input_hash = jma_role_input_hash(
                      job_postings.title,
                      job_postings.description_text
                  )
                  AND job_postings.last_seen_at >= ?
            )
            SELECT job_skills.skill_code,
                   COUNT(DISTINCT selected_current_role_runs.job_posting_id)
                       AS posting_count
            FROM selected_current_role_runs
            JOIN job_postings
              ON job_postings.id = selected_current_role_runs.job_posting_id
            JOIN analysis_runs current_skill_runs
              ON current_skill_runs.job_posting_id =
                 selected_current_role_runs.job_posting_id
             AND current_skill_runs.analyzer_kind = ?
             AND current_skill_runs.taxonomy_version = ?
             AND current_skill_runs.extractor_version = ?
             AND current_skill_runs.input_hash = jma_skill_input_hash(
                 job_postings.title,
                 job_postings.description_text,
                 job_postings.source_tags_json
             )
            JOIN job_skills
              ON job_skills.analysis_run_id = current_skill_runs.id
            GROUP BY job_skills.skill_code
            ORDER BY posting_count DESC, job_skills.skill_code ASC
            LIMIT ?
            """,
            (
                role_code,
                ROLE_ANALYZER_KIND,
                ROLE_TAXONOMY_VERSION,
                ROLE_TAXONOMY_VERSION,
                self._active_cutoff(),
                SKILL_ANALYZER_KIND,
                SKILL_TAXONOMY_VERSION,
                SKILL_TAXONOMY_VERSION,
                top_limit,
            ),
        ).fetchall()
        return RoleDetail(
            role_code=role_code,
            role_name=role_name,
            posting_count=page.posting_count,
            top_skills=tuple(_skill_count(row) for row in rows),
            representative_postings=page.items,
        )

    def get_skill_detail(
        self,
        skill_code: str,
        *,
        top_limit: int = 10,
        posting_limit: int = 5,
    ) -> SkillDetail | None:
        """Return current roles and distinct co-skills for one active skill."""

        _validate_bounded_limit(top_limit, "top_limit", MAX_AGGREGATE_LIMIT)
        _validate_bounded_limit(posting_limit, "posting_limit", MAX_PAGE_SIZE)
        skill_name = _SKILL_NAMES.get(skill_code)
        if skill_name is None:
            return None
        page = self.list_postings(
            PostingSearchFilters(skill_code=skill_code),
            limit=posting_limit,
        )
        associations = self._connection.execute(
            """
            WITH selected_current_skill_runs AS (
                SELECT DISTINCT analysis_runs.id, analysis_runs.job_posting_id
                FROM job_skills selected_skill
                JOIN analysis_runs
                  ON analysis_runs.id = selected_skill.analysis_run_id
                JOIN job_postings
                  ON job_postings.id = analysis_runs.job_posting_id
                WHERE selected_skill.skill_code = ?
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                  AND analysis_runs.input_hash = jma_skill_input_hash(
                      job_postings.title,
                      job_postings.description_text,
                      job_postings.source_tags_json
                  )
                  AND job_postings.last_seen_at >= ?
            )
            , role_counts AS (
                SELECT job_roles.role_code AS code,
                       COUNT(DISTINCT selected_current_skill_runs.job_posting_id)
                           AS posting_count
                FROM selected_current_skill_runs
                JOIN job_postings
                  ON job_postings.id = selected_current_skill_runs.job_posting_id
                JOIN analysis_runs current_role_runs
                  ON current_role_runs.job_posting_id =
                     selected_current_skill_runs.job_posting_id
                 AND current_role_runs.analyzer_kind = ?
                 AND current_role_runs.taxonomy_version = ?
                 AND current_role_runs.extractor_version = ?
                 AND current_role_runs.input_hash = jma_role_input_hash(
                     job_postings.title,
                     job_postings.description_text
                 )
                JOIN job_roles
                  ON job_roles.analysis_run_id = current_role_runs.id
                GROUP BY job_roles.role_code
                ORDER BY posting_count DESC, job_roles.role_code ASC
                LIMIT ?
            ),
            co_skill_counts AS (
                SELECT other_skill.skill_code AS code,
                       COUNT(DISTINCT selected_current_skill_runs.job_posting_id)
                           AS posting_count
                FROM selected_current_skill_runs
                JOIN job_skills other_skill
                  ON other_skill.analysis_run_id = selected_current_skill_runs.id
                 AND other_skill.skill_code != ?
                GROUP BY other_skill.skill_code
                ORDER BY posting_count DESC, other_skill.skill_code ASC
                LIMIT ?
            )
            SELECT 'role' AS association_kind, code, posting_count
            FROM role_counts
            UNION ALL
            SELECT 'skill' AS association_kind, code, posting_count
            FROM co_skill_counts
            """,
            (
                skill_code,
                SKILL_ANALYZER_KIND,
                SKILL_TAXONOMY_VERSION,
                SKILL_TAXONOMY_VERSION,
                self._active_cutoff(),
                ROLE_ANALYZER_KIND,
                ROLE_TAXONOMY_VERSION,
                ROLE_TAXONOMY_VERSION,
                top_limit,
                skill_code,
                top_limit,
            ),
        ).fetchall()
        top_roles = tuple(
            RoleCount(
                role_code=row["code"],
                role_name=_ROLE_NAMES.get(row["code"], row["code"]),
                posting_count=row["posting_count"],
            )
            for row in associations
            if row["association_kind"] == "role"
        )
        co_skills = tuple(
            SkillCount(
                skill_code=row["code"],
                skill_name=_SKILL_NAMES.get(row["code"], row["code"]),
                posting_count=row["posting_count"],
            )
            for row in associations
            if row["association_kind"] == "skill"
        )
        return SkillDetail(
            skill_code=skill_code,
            skill_name=skill_name,
            posting_count=page.posting_count,
            top_roles=top_roles,
            co_occurring_skills=co_skills,
            representative_postings=page.items,
        )

    def list_source_summaries(self) -> tuple[SourceSummary, ...]:
        """Return provider-level freshness and exact-current coverage."""

        summaries_ctes, summaries_parameters = _runs_ctes(
            ROLE_ANALYZER_KIND, SKILL_ANALYZER_KIND
        )
        rows = self._connection.execute(
            summaries_ctes
            + """
            , role_state AS (
                SELECT current_role_runs.job_posting_id,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM job_roles
                           WHERE job_roles.analysis_run_id = current_role_runs.id
                       ) THEN 1 ELSE 0 END AS has_results
                FROM current_role_runs
            ),
            skill_state AS (
                SELECT current_skill_runs.job_posting_id,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM job_skills
                           WHERE job_skills.analysis_run_id = current_skill_runs.id
                       ) THEN 1 ELSE 0 END AS has_results
                FROM current_skill_runs
            )
            SELECT
                job_postings.source_provider,
                COUNT(*) AS posting_count,
                MAX(job_postings.published_at) AS newest_published_at,
                MAX(job_postings.last_seen_at) AS newest_last_seen_at,
                SUM(CASE WHEN role_state.has_results = 1 THEN 1 ELSE 0 END)
                    AS role_classified,
                SUM(CASE WHEN role_state.has_results = 0 THEN 1 ELSE 0 END)
                    AS role_zero,
                SUM(CASE WHEN role_state.job_posting_id IS NULL THEN 1 ELSE 0 END)
                    AS role_not_analyzed,
                SUM(CASE WHEN skill_state.has_results = 1 THEN 1 ELSE 0 END)
                    AS skill_classified,
                SUM(CASE WHEN skill_state.has_results = 0 THEN 1 ELSE 0 END)
                    AS skill_zero,
                SUM(CASE WHEN skill_state.job_posting_id IS NULL THEN 1 ELSE 0 END)
                    AS skill_not_analyzed
            FROM job_postings
            LEFT JOIN role_state
              ON role_state.job_posting_id = job_postings.id
            LEFT JOIN skill_state
              ON skill_state.job_posting_id = job_postings.id
            WHERE job_postings.last_seen_at >= ?
            GROUP BY job_postings.source_provider
            ORDER BY posting_count DESC, job_postings.source_provider ASC
            """,
            (
                self._active_cutoff(),
                *summaries_parameters,
                self._active_cutoff(),
            ),
        ).fetchall()
        return tuple(_source_summary(row) for row in rows)

    def _page_intelligence(
        self,
        rows: Iterable[sqlite3.Row],
    ) -> tuple[
        dict[str, tuple[NamedRole, ...]],
        dict[str, tuple[NamedSkill, ...]],
        dict[str, NamedTerm],
        dict[str, tuple[NamedTerm, ...]],
        dict[str, sqlite3.Row],
        frozenset[str],
        frozenset[str],
    ]:
        rows = tuple(rows)
        if not rows:
            return {}, {}, {}, {}, {}, frozenset(), frozenset()
        role_run_ids = tuple(
            row["role_run_id"] for row in rows if row["role_run_id"] is not None
        )
        skill_run_ids = tuple(
            row["skill_run_id"] for row in rows if row["skill_run_id"] is not None
        )
        seniority_run_ids = tuple(
            row["seniority_run_id"]
            for row in rows
            if row["seniority_run_id"] is not None
        )
        geography_run_ids = tuple(
            row["geography_run_id"]
            for row in rows
            if row["geography_run_id"] is not None
        )
        salary_run_ids = tuple(
            row["salary_run_id"] for row in rows if row["salary_run_id"] is not None
        )
        roles = self._page_role_rows(role_run_ids)
        skills = self._page_skill_rows(skill_run_ids)
        seniority_rows = self._page_seniority_rows(seniority_run_ids)
        geography_rows = self._page_geography_rows(geography_run_ids)
        salary_rows = self._page_salary_rows(salary_run_ids)
        roles_by_posting: defaultdict[str, list[NamedRole]] = defaultdict(list)
        for row in roles:
            if row["role_code"] is None:
                continue
            roles_by_posting[row["job_posting_id"]].append(
                NamedRole(
                    role_code=row["role_code"],
                    role_name=_ROLE_NAMES.get(row["role_code"], row["role_code"]),
                )
            )
        skills_by_posting: defaultdict[str, list[NamedSkill]] = defaultdict(list)
        for row in skills:
            if row["skill_code"] is None:
                continue
            skills_by_posting[row["job_posting_id"]].append(
                NamedSkill(
                    skill_code=row["skill_code"],
                    skill_name=_SKILL_NAMES.get(row["skill_code"], row["skill_code"]),
                )
            )
        seniority_by_posting: dict[str, NamedTerm] = {}
        for row in seniority_rows:
            if row["seniority_code"] is None:
                continue
            seniority_by_posting[row["job_posting_id"]] = NamedTerm(
                code=row["seniority_code"],
                name=_SENIORITY_NAMES.get(
                    row["seniority_code"], row["seniority_code"]
                ),
            )
        geography_terms_by_posting: defaultdict[str, list[NamedTerm]] = defaultdict(
            list
        )
        for row in geography_rows:
            if row["geography_code"] is None:
                continue
            geography_terms_by_posting[row["job_posting_id"]].append(
                NamedTerm(
                    code=row["geography_code"],
                    name=row["geography_name"]
                    or _GEOGRAPHY_NAMES.get(row["geography_code"], row["geography_code"]),
                )
            )
        salary_by_posting = {row["job_posting_id"]: row for row in salary_rows}
        geography_by_posting = {
            key: tuple(value)
            for key, value in geography_terms_by_posting.items()
        }
        return (
            {key: tuple(value) for key, value in roles_by_posting.items()},
            {key: tuple(value) for key, value in skills_by_posting.items()},
            seniority_by_posting,
            geography_by_posting,
            salary_by_posting,
            frozenset(row["job_posting_id"] for row in roles),
            frozenset(row["job_posting_id"] for row in skills),
        )

    def _page_seniority_rows(
        self, run_ids: tuple[str, ...]
    ) -> tuple[sqlite3.Row, ...]:
        if not run_ids:
            return ()
        placeholders = ", ".join("?" for _ in run_ids)
        return tuple(
            self._connection.execute(
                f"""
                SELECT analysis_runs.job_posting_id,
                       job_seniority.seniority_code
                FROM analysis_runs
                JOIN job_postings
                  ON job_postings.id = analysis_runs.job_posting_id
                JOIN job_seniority
                  ON job_seniority.analysis_run_id = analysis_runs.id
                WHERE analysis_runs.id IN ({placeholders})
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                  AND analysis_runs.input_hash = jma_seniority_input_hash(
                      job_postings.title
                  )
                ORDER BY analysis_runs.job_posting_id
                """,
                (
                    *run_ids,
                    SENIORITY_ANALYZER_KIND,
                    SENIORITY_TAXONOMY_VERSION,
                    SENIORITY_TAXONOMY_VERSION,
                ),
            ).fetchall()
        )

    def _page_geography_rows(
        self, run_ids: tuple[str, ...]
    ) -> tuple[sqlite3.Row, ...]:
        if not run_ids:
            return ()
        placeholders = ", ".join("?" for _ in run_ids)
        return tuple(
            self._connection.execute(
                f"""
                SELECT DISTINCT analysis_runs.job_posting_id,
                       job_geography.geography_code,
                       job_geography.geography_name
                FROM analysis_runs
                JOIN job_postings
                  ON job_postings.id = analysis_runs.job_posting_id
                JOIN job_geography
                  ON job_geography.analysis_run_id = analysis_runs.id
                WHERE analysis_runs.id IN ({placeholders})
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                  AND analysis_runs.input_hash = jma_geography_input_hash(
                      job_postings.description_text,
                      job_postings.location_text,
                      job_postings.is_remote
                  )
                ORDER BY analysis_runs.job_posting_id,
                         job_geography.geography_code
                """,
                (
                    *run_ids,
                    GEOGRAPHY_ANALYZER_KIND,
                    GEOGRAPHY_TAXONOMY_VERSION,
                    GEOGRAPHY_TAXONOMY_VERSION,
                ),
            ).fetchall()
        )

    def _page_salary_rows(
        self, run_ids: tuple[str, ...]
    ) -> tuple[sqlite3.Row, ...]:
        if not run_ids:
            return ()
        placeholders = ", ".join("?" for _ in run_ids)
        return tuple(
            self._connection.execute(
                f"""
                SELECT analysis_runs.job_posting_id,
                       job_salaries.currency,
                       job_salaries.annual_min,
                       job_salaries.annual_max
                FROM analysis_runs
                JOIN job_salaries
                  ON job_salaries.analysis_run_id = analysis_runs.id
                WHERE analysis_runs.id IN ({placeholders})
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                """,
                (
                    *run_ids,
                    SALARY_ANALYZER_KIND,
                    SALARY_TAXONOMY_VERSION,
                    SALARY_TAXONOMY_VERSION,
                ),
            ).fetchall()
        )

    def _page_role_rows(self, run_ids: tuple[str, ...]) -> tuple[sqlite3.Row, ...]:
        if not run_ids:
            return ()
        placeholders = ", ".join("?" for _ in run_ids)
        return tuple(
            self._connection.execute(
                f"""
                SELECT analysis_runs.job_posting_id, job_roles.role_code
                FROM analysis_runs
                JOIN job_postings
                  ON job_postings.id = analysis_runs.job_posting_id
                LEFT JOIN job_roles
                  ON job_roles.analysis_run_id = analysis_runs.id
                WHERE analysis_runs.id IN ({placeholders})
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                  AND analysis_runs.input_hash = jma_role_input_hash(
                      job_postings.title,
                      job_postings.description_text
                  )
                ORDER BY analysis_runs.job_posting_id, job_roles.role_code
                """,
                (
                    *run_ids,
                    ROLE_ANALYZER_KIND,
                    ROLE_TAXONOMY_VERSION,
                    ROLE_TAXONOMY_VERSION,
                ),
            ).fetchall()
        )

    def _page_skill_rows(self, run_ids: tuple[str, ...]) -> tuple[sqlite3.Row, ...]:
        if not run_ids:
            return ()
        placeholders = ", ".join("?" for _ in run_ids)
        return tuple(
            self._connection.execute(
                f"""
                SELECT DISTINCT analysis_runs.job_posting_id, job_skills.skill_code
                FROM analysis_runs
                JOIN job_postings
                  ON job_postings.id = analysis_runs.job_posting_id
                LEFT JOIN job_skills
                  ON job_skills.analysis_run_id = analysis_runs.id
                WHERE analysis_runs.id IN ({placeholders})
                  AND analysis_runs.analyzer_kind = ?
                  AND analysis_runs.taxonomy_version = ?
                  AND analysis_runs.extractor_version = ?
                  AND analysis_runs.input_hash = jma_skill_input_hash(
                      job_postings.title,
                      job_postings.description_text,
                      job_postings.source_tags_json
                  )
                ORDER BY analysis_runs.job_posting_id, job_skills.skill_code
                """,
                (
                    *run_ids,
                    SKILL_ANALYZER_KIND,
                    SKILL_TAXONOMY_VERSION,
                    SKILL_TAXONOMY_VERSION,
                ),
            ).fetchall()
        )

    @staticmethod
    def _current_run_parameters() -> tuple[str, ...]:
        return (
            ROLE_ANALYZER_KIND,
            ROLE_TAXONOMY_VERSION,
            ROLE_TAXONOMY_VERSION,
            SKILL_ANALYZER_KIND,
            SKILL_TAXONOMY_VERSION,
            SKILL_TAXONOMY_VERSION,
            SENIORITY_ANALYZER_KIND,
            SENIORITY_TAXONOMY_VERSION,
            SENIORITY_TAXONOMY_VERSION,
            GEOGRAPHY_ANALYZER_KIND,
            GEOGRAPHY_TAXONOMY_VERSION,
            GEOGRAPHY_TAXONOMY_VERSION,
            SALARY_ANALYZER_KIND,
            SALARY_TAXONOMY_VERSION,
            SALARY_TAXONOMY_VERSION,
        )


@lru_cache(maxsize=8192)
def _calculate_persisted_skill_input_hash(
    title: str,
    description_text: str | None,
    source_tags_json: str,
) -> str:
    return calculate_skill_input_hash(
        title,
        description_text,
        deserialize_source_tags(source_tags_json),
    )


@lru_cache(maxsize=8192)
def _calculate_persisted_seniority_input_hash(title: str) -> str:
    return calculate_seniority_input_hash(title)


@lru_cache(maxsize=8192)
def _calculate_persisted_geography_input_hash(
    description_text: str | None,
    location_text: str | None,
    is_remote: int | None,
) -> str:
    is_remote_flag = None if is_remote is None else bool(is_remote)
    return calculate_geography_input_hash(
        description_text,
        location_text=location_text,
        is_remote=is_remote_flag,
    )


@lru_cache(maxsize=8192)
def _calculate_persisted_salary_input_hash(
    salary_text: str | None,
    salary_min: str | None,
    salary_max: str | None,
    salary_currency: str | None,
    salary_period: str | None,
) -> str:
    return calculate_salary_input_hash(
        salary_text,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_period=salary_period,
    )


def _decimal_string(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    formatted = format(quantized, "f").rstrip("0").rstrip(".")
    return formatted or "0"


def _validate_bounded_limit(value: int, name: str, maximum: int) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= maximum
    ):
        raise ValueError(f"{name} must be between 1 and {maximum}")


def _posting_filter_sql(filters: PostingSearchFilters) -> tuple[str, tuple[object, ...]]:
    clauses = ["1 = 1"]
    parameters: list[object] = []
    if filters.source_provider is not None:
        clauses.append("job_postings.source_provider = ?")
        parameters.append(filters.source_provider)
    if filters.role_code is not None:
        clauses.append(
            """EXISTS (
                SELECT 1
                FROM analysis_runs filtered_role_runs
                JOIN job_roles filtered_roles
                  ON filtered_roles.analysis_run_id = filtered_role_runs.id
                WHERE filtered_role_runs.job_posting_id = job_postings.id
                  AND filtered_role_runs.analyzer_kind = ?
                  AND filtered_role_runs.taxonomy_version = ?
                  AND filtered_role_runs.extractor_version = ?
                  AND filtered_role_runs.input_hash = jma_role_input_hash(
                      job_postings.title,
                      job_postings.description_text
                  )
                  AND filtered_roles.role_code = ?
            )"""
        )
        parameters.extend(
            (
                ROLE_ANALYZER_KIND,
                ROLE_TAXONOMY_VERSION,
                ROLE_TAXONOMY_VERSION,
                filters.role_code,
            )
        )
    if filters.skill_code is not None:
        clauses.append(
            """EXISTS (
                SELECT 1
                FROM analysis_runs filtered_skill_runs
                JOIN job_skills filtered_skills
                  ON filtered_skills.analysis_run_id = filtered_skill_runs.id
                WHERE filtered_skill_runs.job_posting_id = job_postings.id
                  AND filtered_skill_runs.analyzer_kind = ?
                  AND filtered_skill_runs.taxonomy_version = ?
                  AND filtered_skill_runs.extractor_version = ?
                  AND filtered_skill_runs.input_hash = jma_skill_input_hash(
                      job_postings.title,
                      job_postings.description_text,
                      job_postings.source_tags_json
                  )
                  AND filtered_skills.skill_code = ?
            )"""
        )
        parameters.extend(
            (
                SKILL_ANALYZER_KIND,
                SKILL_TAXONOMY_VERSION,
                SKILL_TAXONOMY_VERSION,
                filters.skill_code,
            )
        )
    if filters.seniority_code is not None:
        clauses.append(
            """EXISTS (
                SELECT 1
                FROM analysis_runs filtered_seniority_runs
                JOIN job_seniority filtered_seniority
                  ON filtered_seniority.analysis_run_id =
                     filtered_seniority_runs.id
                WHERE filtered_seniority_runs.job_posting_id = job_postings.id
                  AND filtered_seniority_runs.analyzer_kind = ?
                  AND filtered_seniority_runs.taxonomy_version = ?
                  AND filtered_seniority_runs.extractor_version = ?
                  AND filtered_seniority_runs.input_hash =
                      jma_seniority_input_hash(job_postings.title)
                  AND filtered_seniority.seniority_code = ?
            )"""
        )
        parameters.extend(
            (
                SENIORITY_ANALYZER_KIND,
                SENIORITY_TAXONOMY_VERSION,
                SENIORITY_TAXONOMY_VERSION,
                filters.seniority_code,
            )
        )
    if filters.geography_code is not None:
        clauses.append(
            """EXISTS (
                SELECT 1
                FROM analysis_runs filtered_geography_runs
                JOIN job_geography filtered_geography
                  ON filtered_geography.analysis_run_id =
                     filtered_geography_runs.id
                WHERE filtered_geography_runs.job_posting_id = job_postings.id
                  AND filtered_geography_runs.analyzer_kind = ?
                  AND filtered_geography_runs.taxonomy_version = ?
                  AND filtered_geography_runs.extractor_version = ?
                  AND filtered_geography_runs.input_hash =
                      jma_geography_input_hash(
                          job_postings.description_text,
                          job_postings.location_text,
                          job_postings.is_remote
                      )
                  AND filtered_geography.geography_code = ?
            )"""
        )
        parameters.extend(
            (
                GEOGRAPHY_ANALYZER_KIND,
                GEOGRAPHY_TAXONOMY_VERSION,
                GEOGRAPHY_TAXONOMY_VERSION,
                filters.geography_code,
            )
        )
    if filters.has_salary is not None:
        clause = (
            "EXISTS ("
            "SELECT 1 FROM analysis_runs filtered_salary_runs"
            " JOIN job_salaries filtered_salaries"
            " ON filtered_salaries.analysis_run_id = filtered_salary_runs.id"
            " WHERE filtered_salary_runs.job_posting_id = job_postings.id"
            " AND filtered_salary_runs.analyzer_kind = ?"
            " AND filtered_salary_runs.taxonomy_version = ?"
            " AND filtered_salary_runs.extractor_version = ?"
            " AND filtered_salary_runs.input_hash = jma_salary_input_hash("
            " job_postings.salary_text, job_postings.salary_min,"
            " job_postings.salary_max, job_postings.salary_currency,"
            " job_postings.salary_period)"
            ")"
        )
        if not filters.has_salary:
            clause = f"NOT {clause}"
        clauses.append(clause)
        parameters.extend(
            (
                SALARY_ANALYZER_KIND,
                SALARY_TAXONOMY_VERSION,
                SALARY_TAXONOMY_VERSION,
            )
        )
    if filters.search_text is not None:
        escaped = _escape_like(filters.search_text)
        clauses.append(
            """(
                job_postings.title LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR COALESCE(job_postings.company_name, '')
                   LIKE ? ESCAPE '\\' COLLATE NOCASE
            )"""
        )
        parameters.extend((f"%{escaped}%", f"%{escaped}%"))
    return " AND ".join(clauses), tuple(parameters)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _posting_list_item(
    row: sqlite3.Row,
    roles: tuple[NamedRole, ...],
    skills: tuple[NamedSkill, ...],
    *,
    seniority: NamedTerm | None,
    geography: tuple[NamedTerm, ...],
    salary: sqlite3.Row | None,
    role_run_is_current: bool,
    skill_run_is_current: bool,
) -> PostingListItem:
    arrangement = next(
        (term for term in geography if term.code.startswith("arrangement_")),
        None,
    )
    regions = tuple(term for term in geography if term.code.startswith("region_"))
    return PostingListItem(
        job_posting_id=UUID(row["id"]),
        canonical_job_id=UUID(row["canonical_job_id"]),
        source_provider=row["source_provider"],
        source_scope=row["source_scope"],
        external_id=row["external_id"],
        company_name=row["company_name"],
        title=row["title"],
        location=row["location_text"],
        published_at=_deserialize_datetime(row["published_at"]),
        source_url=row["source_url"],
        application_url=row["application_url"],
        role_analysis_status=_analysis_status(role_run_is_current, roles),
        skill_analysis_status=_analysis_status(skill_run_is_current, skills),
        roles=roles,
        skills=skills,
        seniority=seniority,
        arrangement=arrangement,
        regions=regions,
        salary_currency=salary["currency"] if salary is not None else None,
        salary_annual_min=salary["annual_min"] if salary is not None else None,
        salary_annual_max=salary["annual_max"] if salary is not None else None,
    )


def _analysis_status(
    run_is_current: bool,
    evidence: tuple[object, ...],
) -> AnalysisStatus:
    if not run_is_current:
        return AnalysisStatus.NOT_ANALYZED
    if not evidence:
        return AnalysisStatus.ANALYZED_ZERO
    return AnalysisStatus.ANALYZED_WITH_RESULTS


def _role_count(row: sqlite3.Row) -> RoleCount:
    code = row["role_code"]
    return RoleCount(
        role_code=code,
        role_name=_ROLE_NAMES.get(code, code),
        posting_count=row["posting_count"],
    )


def _skill_count(row: sqlite3.Row) -> SkillCount:
    code = row["skill_code"]
    return SkillCount(
        skill_code=code,
        skill_name=_SKILL_NAMES.get(code, code),
        posting_count=row["posting_count"],
    )


def _role_count_dict(row: dict[str, object]) -> RoleCount:
    code = str(row["role_code"])
    return RoleCount(
        role_code=code,
        role_name=_ROLE_NAMES.get(code, code),
        posting_count=int(row["posting_count"]),
    )


def _skill_count_dict(row: dict[str, object]) -> SkillCount:
    code = str(row["skill_code"])
    return SkillCount(
        skill_code=code,
        skill_name=_SKILL_NAMES.get(code, code),
        posting_count=int(row["posting_count"]),
    )


def _source_summary(row: sqlite3.Row) -> SourceSummary:
    posting_count = row["posting_count"]
    role_classified = row["role_classified"] or 0
    skill_classified = row["skill_classified"] or 0
    return SourceSummary(
        source_provider=row["source_provider"],
        posting_count=posting_count,
        newest_published_at=_deserialize_datetime(row["newest_published_at"]),
        newest_last_seen_at=_required_datetime(row["newest_last_seen_at"]),
        current_role_classified_posting_count=role_classified,
        current_role_unknown_posting_count=row["role_zero"] or 0,
        current_role_not_analyzed_posting_count=row["role_not_analyzed"] or 0,
        current_role_classified_percentage=100.0 * role_classified / posting_count,
        current_skill_classified_posting_count=skill_classified,
        current_skill_zero_posting_count=row["skill_zero"] or 0,
        current_skill_not_analyzed_posting_count=row["skill_not_analyzed"] or 0,
        current_skill_classified_percentage=100.0 * skill_classified / posting_count,
    )


def _deserialize_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _required_datetime(value: str) -> datetime:
    parsed = _deserialize_datetime(value)
    if parsed is None:
        raise ValueError("required persisted datetime is missing")
    return parsed
