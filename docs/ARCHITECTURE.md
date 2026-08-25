# Architecture

## Goal

Build a maintainable system that collects remote job listings from a small number of reliable sources and preserves enough provenance for later market analysis.

## Current MVP Pipeline

External sources
↓
Independent collectors
↓
RawJob
↓
Normalizer
↓
NormalizedJobPosting
↓
JobRepository persistence boundary
↓
JobPosting
↓
CanonicalJob
↓
Pure deterministic intelligence extraction
├─ SkillEvidence → versioned analysis_runs + job_skills
├─ RoleEvidence → versioned analysis_runs + job_roles
├─ SeniorityEvidence → versioned analysis_runs + job_seniority
├─ GeographyEvidence → versioned analysis_runs + job_geography
└─ SalaryEstimate → versioned analysis_runs + job_salaries
↓
Read-only posting-level analytics repository
↓
Local read-only HTTP API
↓
Browser Dashboard v0
↓
Later high-confidence canonical-job analytics

## Core Models

### RawJob

An immutable source observation collected at a specific time. It contains source identity metadata and the original JSON-like payload, but no persistent JobPosting ID.

Raw provenance is mandatory. The first observation and every changed observation are stored. An immediately unchanged observation updates the posting lifecycle without duplicating its JSON payload.

`latest_observation_hash` follows persistence arrival order: it is the hash of the most recently persisted observation, even when that observation has an older `fetched_at`. Current normalized JobPosting state and monotonic `last_seen_at` follow event-time freshness, so a stale observation may extend raw provenance and advance `latest_observation_hash` without overwriting newer normalized state.

### NormalizedJobPosting

The normalized source-level vacancy before persistence. It has no database ID, canonical ID, lifecycle timestamps, or persistence hashes. Its `source_tags` field is a deterministic tuple of source-observed labels. These labels are normalized inputs, not canonical skills or role classifications; the original raw payload remains authoritative provenance.

### JobPosting

A durable posting on one source. Its stable identity is:

`(source_provider, source_scope, external_id)`

Repeated collection updates the same JobPosting. It stores normalized source-level fields, first/last seen timestamps, and the persistence-owned `content_hash`.

### CanonicalJob

A minimal grouping identity for one real-world vacancy. Multiple source-specific JobPostings may belong to one CanonicalJob. Source-level descriptions, salary, location, and publication dates remain on JobPosting records.

## Identity and Deduplication

Two operations remain separate:

1. Same-source upsert resolves a JobPosting by source provider, scope, and external ID.
2. Cross-source canonical linking groups distinct JobPostings without deleting them.

A new posting without a high-confidence match receives a new CanonicalJob. Low-confidence matches are not merged automatically. Analytics normally count CanonicalJobs while retaining every source posting for provenance.

## Persistence Boundary

Application services depend on the `JobRepository` protocol, not SQLite. A repository accepts `RawJob` plus `NormalizedJobPosting` and owns durable IDs, lifecycle timestamps, hashes, transactions, and raw-to-posting links.

### Guided update orchestration

The one-shot `update` application service coordinates existing components without
reimplementing them. A small static source registry binds a provider code and display
name to its existing collector factory and normalizer, plus only the credential
metadata needed for an honest skip. A separate analyzer registry binds
`(analyzer_kind, input_language)` to a version and existing durable-posting runner.
Source identity is never used as a language signal; a source may contain mixed text.

The update validates that every active analyzer kind supports the requested input
language before opening the database or collecting. Current capability is
`skills/en`, `roles/en`, `seniority/en`, `geography/en`, and `salary/en`; no
Ukrainian implementation is registered. Enabled
sources then run sequentially in registry order. A collector/network failure is an
isolated source result and later sources continue. Normalization invariants outside
the existing typed recoverable item failures, repository writes, schema errors, and
database errors are systemic and abort. Analysis reloads current durable postings
through the existing repository after collection, so it never analyzes stale
collector objects. Analyzer failures are visible and independent unless SQLite or an
open transaction indicates a systemic consistency failure.

The registry is an explicit composition root, not a plugin framework. Adding a
source changes its adapter module plus the registry entry; adding a language changes
the relevant language-specific analyzer registrations. The CLI only selects and
reports these entries. No scheduler, background worker, language detection, or schema
change is part of this flow.

Persistence uses deterministic representations:

- timestamps: UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`;
- Decimal values: exact canonical decimal strings without floats;
- payloads: compact UTF-8 JSON with sorted keys and non-finite numbers rejected;
- source tags: compact canonical JSON arrays with deterministic order;
- `observation_hash`: calculated by persistence from source identity, source URL, and raw payload;
- `content_hash`: calculated by persistence from an explicit set of normalized source-level fields, including `source_tags`.

The SQLite schema stores three authoritative source/domain tables:

- `canonical_jobs`;
- `job_postings`;
- `raw_jobs`.

Replaceable skill and role intelligence is stored separately in:

- `skills`, a small stable-code reference table;
- `analysis_runs`, one row per posting, analyzer/version, and dedicated input hash;
- `job_skills`, direct mention evidence owned by one analysis run, including the
  evidence-time skill display-name snapshot.
- `roles`, a stable language-neutral role-code reference table;
- `job_roles`, deterministic role evidence with an evidence-time role-name
  snapshot.

`SkillIntelligenceRepository` and `RoleIntelligenceRepository` are separate from `JobRepository`. Each repository atomically commits one analysis run, its reference rows, and its analyzer-specific evidence. Database constraints prevent skill evidence from attaching to role runs and role evidence from attaching to skill runs on both insert and reassignment. The five fields that define an analysis-run identity are immutable after insertion, preventing existing evidence from being reinterpreted under another analyzer or input identity. Derived rows may cascade when their `JobPosting` is deleted; source/domain rows never depend on derived intelligence.

SQLite initialization reads `PRAGMA user_version` before application DDL. Versions newer than the supported schema fail without mutation. Committed v1 is structurally validated before the additive v2 skill migration; valid v2 is structurally validated before the additive v3 role migration. Unexpected partial intelligence objects are rejected, and current v6 must pass critical table, column, key, index, trigger, constraint, and foreign-key checks. Migration creates no role-analysis backfill.

## Internal Analytics Boundary

`AnalyticsRepository` is a separate read-only boundary for Dashboard v0; it does not
extend or overload the write-oriented `JobRepository` or intelligence repositories.
Its SQLite implementation uses bounded, parameterized aggregate/list queries and
returns immutable DTOs rather than `sqlite3.Row`, connections, descriptions, or raw
payloads. No additional service layer exists yet because the repository already owns
the complete storage-independent query contract and there is no separate application
policy to orchestrate.

Dashboard v0 analytics count durable source postings by default. Field names say
`posting_count`, and results do not claim complete cross-source deduplication. The
posting list carries `canonical_job_id` for provenance/future grouping, but no fuzzy
linking or misleading global unique-job total is introduced.

Job Lifecycle v1 adds a read-time freshness boundary: analytics queries consider a
posting active only when its `last_seen_at` is within
`ACTIVE_POSTING_WINDOW_DAYS = 30` of the repository clock, which is injectable for
deterministic tests. Stale postings disappear from default overview, list, detail,
and source summaries while remaining durably stored with all observations, per
ADR-020's status-not-deletion rule. `GET /api/jobs` accepts an explicit
`include_stale=true` parameter for history access; no persisted lifecycle column,
removal policy, or source-provided expiry handling exists yet.

Current intelligence is resolved by exact analyzer kind, active taxonomy/extractor
version, and the current posting input hash. Historical runs are never selected by
creation time. An exact run with no evidence is analyzed-zero (Unknown for roles),
while no exact compatible run is not-analyzed. Role and skill aggregates count each
posting once even when several evidence rows exist.

The contract covers overview, deterministic paginated posting search, role detail,
skill detail/co-occurrence, and source dataset summaries. Stable role/skill codes are
filter identity; current English names are replaceable display labels. Details are in
`docs/ANALYTICS_QUERY_CONTRACT.md`.

## Local API Boundary

The local Dashboard API is a thin FastAPI adapter over `AnalyticsRepository`. HTTP
handlers validate bounded query/path input, invoke repository methods, and map the
immutable DTOs into explicit Pydantic response models. They contain no SQL, current-
run selection, historical filtering, or distinct-count logic.

The `serve` CLI requires an existing current-schema database, accepts only loopback
bind hosts, and defaults to `127.0.0.1:8000`. Startup opens SQLite with `mode=ro`, validates schema v6 without
migration, and stores only the validated path as application configuration. Every
request creates its own read-only, `query_only` connection and closes it after the
response; no SQLite connection is shared across request threads.

The API exposes only GET endpoints under `/api`. Posting responses exclude full
descriptions and RawJob payloads. Errors have stable codes, generic public messages,
and request IDs without SQL or filesystem paths. Local Dashboard origins on ports
3000 are explicitly allowlisted; authentication and hosted exposure remain postponed.
The HTTP contract is documented in `docs/API_CONTRACT.md`.

## Local Dashboard Boundary

The browser product is isolated in `web/` and does not enter the Python package or
SQLite process. Next.js App Router server components call the local GET-only API
through one typed, timeout-bounded client. The only client component owns active
navigation state; Jobs filters use native URL query parameters, so refresh,
bookmarks, and browser history preserve the selected source, role, skill, text, and
page.

Frontend types mirror the explicit API response models and retain `role_code`,
`skill_code`, and `source_provider` as identity. Presentation helpers format labels
and dates without changing source data. Pages contain no SQL, taxonomy rules,
database paths, source tokens, descriptions, or raw payload rendering. External
vacancy links use a new browsing context with `noopener noreferrer`.

The dashboard is a local read-only consumer, not another application service. It
does not add frontend proxy routes, write APIs, authentication, global state, a chart
library, or a component framework. Product scope and local operation are documented
in `docs/DASHBOARD_V0.md`.

## Collectors

Each source has an independent collector. Prefer sources in this order:

1. REST APIs
2. GraphQL APIs
3. RSS / Atom
4. Public structured JSON
5. Public ATS endpoints
6. HTML scraping only when necessary

Do not bypass authentication, CAPTCHAs, Cloudflare challenges, rate limits, or access restrictions.

Collection runs fail loudly for source-wide HTTP or feed-shape errors. A malformed individual vacancy reported by a collector, or a source normalizer's typed recoverable `NormalizationError`, is recorded in the collection summary while later valid items continue. Unexpected normalizer defects and all repository/storage errors propagate immediately because continuing after a systemic failure could hide data loss or corruption.

## Later Analysis

The first intelligence component is a pure deterministic skill extractor. It consumes only normalized `JobPosting.title`, `JobPosting.description_text`, and `JobPosting.source_tags`. It applies the active analyzer-curated skill taxonomy version `2` and returns immutable `SkillEvidence` records with the canonical skill, source field, matched alias, short evidence snippet, stable rule ID, match kind, and mention kind. Taxonomy v1 remains represented by historical persisted runs; v2 is still curated and intentionally incomplete.

Evidence currently means only that a skill was `mentioned`. It does not claim that the skill is required, preferred, mastered, or central to the vacancy. Absence of `SkillEvidence` means only that the active extractor did not identify a matching rule; it does not prove that the vacancy does not mention or require the skill in reality. Source tags go through the same taxonomy rules as title and description text; unknown tags are not converted into skills. Contextual guards are bypassed for an exact source-tag alias because a tag is structured source-observed evidence rather than free prose.

The extractor has no database, network, AI, LLM, or embedding dependency. A separate application service analyzes a supplied current persisted `JobPosting`, calculates a dedicated SHA-256 hash from only `title`, `description_text`, and normalized `source_tags`, and persists the resulting evidence through `SkillIntelligenceRepository`. `None`, empty, and whitespace-only descriptions share the no-description hash representation. Salary, company, location, URLs, source lifecycle timestamps, and raw observations do not affect this analyzer input hash.

An `analysis_runs` row records analyzer kind, taxonomy version, extractor version, input hash, and creation time. The active taxonomy constant represents the full deterministic extraction semantics and is stored as both version identities. Identical posting/version/input analysis is idempotent, including a successful run with zero evidence. Changed analyzer input or version creates a new historical run; v1 and v2 runs coexist and old runs are not deleted automatically. `skills` stores one row per stable canonical code and preserves the first persisted reference display name instead of changing it according to recomputation order. Each `job_skills` row separately snapshots the extractor-produced `skill_name`, so historical `SkillEvidence` keeps its original label. Aliases and rules remain code-owned taxonomy data.

`analyze_job_skills()` remains a trusted internal service whose caller must supply current persisted state. The source-independent `JobPostingReader` contract and `SQLiteJobRepository.list_job_postings()` reconstruct bounded current `JobPosting` rows through persisted serialization and model validation before the manual one-shot service calls it. The manual CLI never analyzes `RawJob` directly and adds no scheduler or misleading latest-run API. Any future automatic collection-to-analysis orchestration must reuse this durable boundary rather than pass stale collector objects.

Role Classification (taxonomy v2) is a second pure intelligence boundary. It consumes only `title` and optional `description_text`, applies a versioned 19-role taxonomy, and returns immutable direct `RoleEvidence`. Title evidence has precedence; an explicit description role statement is consulted only when the title produces no role. Zero evidence represents Unknown, and directly supported compound titles may produce several roles. Role, seniority, and domain remain separate dimensions.

The pure classifier remains independent of persistence, source-specific logic, networking, AI, and `source_tags`. `analyze_job_roles()` hashes only `title` and the optional description, using the same no-description representation for `None`, empty, and whitespace-only values. It stores versioned historical runs through `RoleIntelligenceRepository`; the current single semantics version is recorded as both taxonomy and extractor version. An analyzed Unknown is an `analysis_runs` row with zero `job_roles`, which differs from a posting never analyzed.

`roles.code` is stable identity and is not English-specific. Its first persisted display label is preserved. Every `job_roles` row stores the exact role-name snapshot and raw matched evidence emitted by that run, so a future label or language change cannot rewrite historical evidence. Aliases, regexes, and taxonomy rules remain code-owned. Identical version/input runs are reused; changed title, description, or version creates another historical run. Company, salary, location, tags, URLs, lifecycle timestamps, and skill output do not affect the role hash.

The role service is a trusted internal boundary for a current persisted `JobPosting`, not `RawJob`. A stale in-memory posting can intentionally create a historical run for stale inputs, so future collection orchestration must reload through the durable current-posting reader before analysis. This persistence is recomputable input evidence, not final role-demand or market analytics. Later derived records may separately cover seniority, salary interpretation, remote geography, and AI-assisted work potential.

The manual `analyze-roles` command reuses `JobPostingReader` and processes its deterministic bounded current-posting order. For each posting it calls `analyze_job_roles()` and computes the command summary only from the exact returned or reused `analysis_run_id`; it does not guess a current run from `created_at`. Unknown is counted from an exact run with zero retrieved evidence, top roles count distinct postings, and evidence, Unknown, and multi-label previews are capped at ten. Any extractor, schema, or repository error aborts the command with a non-zero exit. This is a one-shot local validation boundary with no collection, network access, scheduler, or generic latest-run query.

Seniority Classification V1 is the third deterministic intelligence boundary. It consumes only `title`, applies a versioned experience-axis taxonomy (intern, junior, mid, senior, lead, staff, principal), and returns at most one evidence record by highest-rank precedence; zero evidence is Unknown. People-management words are not seniority evidence because functional titles such as Product Manager would misclassify. Its dedicated input hash covers `title` only, so description edits do not create new seniority runs. Persistence uses schema v4's additive `seniority_levels` and `job_seniority` tables with analyzer-kind triggers, reusing the generic `analysis_runs` identity. The analyzer is registered as `seniority/en` in the guided-update registry; dashboard v2 exposes seniority through overview aggregates and jobs filters.

Geography Classification V1 is the fourth deterministic intelligence boundary. It consumes normalized `description_text`, `location_text`, and the structured `is_remote` flag (titles are excluded to keep runs stable under retitling) and classifies two independent dimensions: one work-arrangement term (`arrangement_remote`, `arrangement_hybrid`, `arrangement_onsite`) where a structured source flag is authoritative, plus multi-label region eligibility (`region_worldwide`, `region_europe`, `region_north_america`, `region_latin_america`, `region_asia_pacific`). Persistence uses schema v5's additive `geography_terms` and `job_geography` tables with analyzer-kind triggers. The analyzer is registered as `geography/en`; dashboard v2 exposes arrangement and region filters plus overview aggregates.

Salary Classification V1 is the fifth deterministic intelligence boundary. It consumes only normalized salary fields and produces at most one estimate per run with explicit provenance (`structured`/`text`) and confidence (`direct`/`parsed`). Annual equivalents are derived only under known periods using documented conventions, unknown periods store null annual figures, equity-only mentions produce no estimate, and inverted ranges are rejected. Persistence uses schema v6's additive `job_salaries` table keyed by analysis run with analyzer-kind triggers. The analyzer is registered as `salary/en`; dashboard v2 exposes salary coverage and per-currency medians in overview projections.

Source Update Run History V1 (schema v7) records one append-only row per guided-update source attempt (`completed`/`failed`/`skipped`) with redacted messages and counts in `source_update_runs`. The guided update orchestrator writes history; analytics join the latest attempt and last success per provider into `/api/sources`, and the Sources page shows "Last successful update" with a visible warning for failed or skipped latest attempts. Production refresh runs the same image's `update` command via a compose overlay plus a systemd timer, so hosted data stays fresh without manual scp.

Canonical analytics remove duplication only when multiple postings already share one `CanonicalJob`. Complete cross-source canonical linking is not implemented yet, so current data must not be described as fully deduplicated across sources.

## Engineering Principles

- Keep collectors independent from normalization, persistence, and analysis.
- Preserve original source payloads and trace every CanonicalJob back to its postings and observations.
- Keep application services independent from CLI, web, bots, and a concrete database.
- Prefer small, explicit modules and deterministic data transformations.
- Document external-source attribution in `docs/SOURCES.md`.
