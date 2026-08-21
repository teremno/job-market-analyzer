# Local Dashboard API Contract

Status: Dashboard v0 local read-only API contract, 2026-08-21.

## Scope

The API is a local-first HTTP adapter over the committed `AnalyticsRepository`.
It validates HTTP input, opens one short-lived read-only SQLite connection, maps
immutable analytics DTOs into explicit Pydantic response models, and returns JSON.
It does not duplicate analytics SQL or current-run resolution.

The API has no authentication because it binds to `127.0.0.1` by default and is not a
hosted or multi-user service. There are no write endpoints, background tasks, RawJob
routes, full-description list fields, AI calls, or collection side effects.

## Startup

```bash
job-market-analyzer serve --database ./jobs.sqlite3
```

`--database` is mandatory and must point to an existing regular SQLite file with the
current schema version. Startup uses a read-only SQLite URI and rejects missing,
legacy, future, malformed, or partially migrated databases. It does not create an
empty database or apply migrations. Defaults are `--host 127.0.0.1` and `--port 8000`;
the valid port range is 1–65535. Host overrides are restricted to loopback addresses
or `localhost`; the CLI rejects public bind addresses such as `0.0.0.0`.

Base URL: `http://127.0.0.1:8000/api`

Interactive OpenAPI remains enabled at `/docs`; the machine schema is
`/openapi.json`.

## Shared semantics

- Counts mean durable source postings, not fully deduplicated real-world jobs.
- Current role/skill evidence is resolved entirely by the analytics layer using exact
  active analyzer versions and current input hashes.
- Historical or stale evidence never becomes current through the API.
- Machine identity uses `role_code`, `skill_code`, and `source_provider`; English
  names are replaceable display labels.
- UUID values are JSON strings and timestamps are ISO 8601 strings.
- Posting projections exclude full descriptions and raw payloads.

## Endpoints

### `GET /api/health`

Confirms that the API can open and query the configured database:

```json
{"status": "ok", "schema_version": 3}
```

It does not report collector health or source freshness and never returns a database
path.

### `GET /api/overview`

Returns `posting_count`, `source_count`, role and skill three-state counts,
`postings_by_source`, `top_roles`, and `top_skills`. Role/skill/source codes remain
first-class identity fields. Aggregate counts are distinct posting counts.

### `GET /api/jobs`

Query parameters:

| Parameter | Contract |
|---|---|
| `limit` | integer 1–100; default 50 |
| `offset` | integer 0–1,000,000; default 0 |
| `source` | exact source provider, maximum 100 characters |
| `role` | exact active role code, maximum 100 characters |
| `skill` | exact active skill code, maximum 100 characters |
| `q` | literal title/company substring, maximum 200 characters |

Filters may be combined. Whitespace-only and overlong strings are rejected. Literal
search retains the analytics layer's escaping and ASCII-oriented case-insensitive
SQLite behavior. Response fields are `items`, `limit`, `offset`, and `total`; ordering
is the deterministic ordering documented in `ANALYTICS_QUERY_CONTRACT.md`.

### `GET /api/roles/{role_code}`

Returns role identity, posting count, skills mentioned among matching postings, and
bounded representative postings. An unknown active-taxonomy code returns 404. A known
code with zero current postings returns 200 with zero/empty results.

### `GET /api/skills/{skill_code}`

Returns skill identity, posting count, associated current roles, co-occurring skills,
and representative postings. Unknown/known-zero behavior matches the role endpoint.

### `GET /api/sources`

Returns deterministic source dataset summaries: posting count, newest published and
last-seen timestamps, plus role/skill `not_analyzed`, `analyzed_zero`,
`analyzed_with_results`, and with-results percentage. These fields are dataset
coverage, not uptime, availability, reliability, or global market share.

## Errors and request IDs

Errors use one stable shape:

```json
{
  "error": {"code": "invalid_request", "message": "Request parameters are invalid."},
  "request_id": "00000000-0000-0000-0000-000000000000"
}
```

Every response also carries `x-request-id`. Expected statuses are:

- 404: unknown role or skill code;
- 422: invalid path/query input;
- 500: unexpected internal failure with a generic message;
- 503: the previously validated database became unavailable.

Responses never include SQL, stack traces, secrets, or absolute database paths. Full
diagnostics and the same request ID are logged locally for unexpected failures.

## Connections, read-only behavior, and CORS

Every request owns one SQLite `mode=ro` connection with `PRAGMA query_only = ON`; the
dependency closes it in `finally`. No connection is shared across request threads.
Startup validation and endpoints do not change database bytes.

Development CORS allows only `http://localhost:3000` and
`http://127.0.0.1:3000`, only GET, and no credentials. Other origins receive no CORS
allow header. This is sufficient for the next local Dashboard v0 sprint without a
wildcard policy.

## Limitations and next consumer

There is no authentication, hosted exposure, rate limiter, cache, cursor pagination,
frontend, salary/seniority/geography normalization, or fuzzy canonical linker. API
overhead is intentionally small relative to SQLite analytics. The next sprint is the
browser Dashboard v0 with Overview, Jobs, Roles, Skills, and Sources screens.
