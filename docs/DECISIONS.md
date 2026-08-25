# Architecture Decision Log

This file records important technical and product decisions.

---

## ADR-001: Primary project goal

Date: 2026-08-17

Status: Accepted

### Decision

The primary goal is job-market analysis rather than real-time job notifications.

### Reason

We want to identify:

- demanded technologies
- skill requirements
- salaries
- entry barriers
- remote availability
- AI leverage

### Consequence

Initial development will prioritize collecting and analyzing job data.

Real-time Telegram/Discord notifications are secondary.

---

## ADR-002: Prefer machine-readable sources

Date: 2026-08-17

Status: Accepted

### Decision

Prefer:

1. REST APIs
2. GraphQL APIs
3. RSS / Atom
4. Public JSON
5. ATS feeds
6. HTML scraping only as fallback

### Reason

Structured sources are more stable, easier to maintain, and easier to normalize.

---

## ADR-003: External code attribution

Date: 2026-08-17

Status: Accepted

### Decision

External repositories may be used as references, but their usage must be documented in SOURCES.md.

Licenses must be checked before copying or adapting code.

---

## ADR-004: Core must be interface-independent

Date: 2026-08-17

Status: Accepted

### Decision

Core business logic must not depend on CLI, web APIs, Telegram bots, or other user interfaces.

User-facing interfaces should call reusable application services.

### Reason

The project may later run as:

- a local CLI application
- a server application
- a REST API
- a web application
- a Telegram bot
- other integrations

Keeping business logic independent allows these interfaces to be added without rewriting collectors, normalization, storage, or analytics.

### Future Direction

The initial MVP will use CLI as the first interface.

Possible future interfaces:

- FastAPI REST API
- web dashboard
- Telegram bot
- Discord integration

These components should be added only after the core collection pipeline is stable.

---

## ADR-005: Separate source postings from canonical jobs

Date: 2026-08-17

Status: Accepted

### Decision

The system will distinguish between a job posting published on a specific source and the underlying real-world job opportunity.

The data model will use three levels:

1. RawJob — original payload collected from a source.
2. JobPosting — normalized representation of a posting on one specific source.
3. CanonicalJob — a logical real-world vacancy that may be represented by multiple JobPostings.

### Reason

The same vacancy may appear on multiple job boards, ATS platforms, aggregators, and company career pages.

Counting each copy independently would distort market statistics such as:

- technology demand
- skill frequency
- salary statistics
- role popularity
- remote-job availability

### Analytics Rule

Market statistics should normally count CanonicalJobs rather than individual JobPostings.

### User Experience

User-facing interfaces may show one CanonicalJob together with all known source URLs where that vacancy was discovered.

### Deduplication Strategy

High-confidence matching may use:

- source-specific IDs
- canonical job URLs
- ATS job identifiers
- company identity
- normalized title
- location
- publication dates
- description similarity

Low-confidence matches must not be merged automatically.

---

## ADR-006: Job identity, lifecycle and provenance

Date: 2026-08-17

Status: Accepted

### Decision

The job data model has three distinct levels:

1. RawJob
2. JobPosting
3. CanonicalJob

These levels have different responsibilities and must not be merged.

### RawJob

RawJob represents an immutable observation collected from an external source at a specific time.

A source posting may produce multiple RawJob observations over time.

RawJob stores:

- source provider
- source scope
- external source ID
- fetched timestamp
- original source payload
- collector metadata needed for routing and identity

Raw observations must preserve provenance and should not be overwritten when the source content changes.

### NormalizedJobPosting

NormalizedJobPosting is an application DTO between normalization and persistence. It contains normalized source-level vacancy data but intentionally has no:

- database ID;
- canonical job ID;
- first-seen or last-seen timestamps;
- persistence hashes.

The repository receives RawJob and NormalizedJobPosting together and verifies that their source identities match.

### JobPosting

JobPosting represents a durable vacancy posting on one specific source.

Its identity is based on:

- source_provider
- source_scope
- external_id

Example:

source_provider = greenhouse
source_scope = example-company
external_id = 123456

A JobPosting may have multiple RawJob observations collected over time.

JobPosting stores normalized source-level information such as:

- title
- company
- description
- location
- remote information
- employment type
- salary information
- publication date
- first_seen_at
- last_seen_at
- content_hash

The persistence layer owns `content_hash`. It calculates the hash from an explicit set of normalized fields and excludes database IDs, canonical relationships, lifecycle timestamps, and persistence metadata.

Repeated collection of the same source posting must update the existing JobPosting rather than create a duplicate posting.

### CanonicalJob

CanonicalJob represents the logical real-world vacancy.

Multiple JobPostings from different sources may belong to one CanonicalJob.

CanonicalJob is primarily a grouping identity.

For the MVP it should not independently duplicate source-level fields such as:

- salary
- description
- publication date
- location

unless a documented resolution policy is introduced later.

### Cardinality

The intended relationship is:

CanonicalJob
  1 -> many JobPostings

JobPosting
  1 -> many RawJob observations

Every JobPosting belongs to exactly one CanonicalJob.

A newly discovered posting that cannot be confidently matched to an existing CanonicalJob receives a new CanonicalJob.

A JobPosting may later be re-linked if a high-confidence match is discovered.

### Deduplication

Two separate operations must remain distinct:

1. Same-source identity/upsert
2. Cross-source canonical linking

Same-source repeated observations must not create duplicate JobPostings.

Cross-source duplicate postings must not be deleted.

They remain separate JobPostings linked to the same CanonicalJob.

### Analytics

Market statistics should normally count CanonicalJobs rather than JobPostings.

Source-level information remains available for provenance and comparison.

### Derived Data

Future AI-derived or analytical fields such as:

- skills
- seniority
- role classification
- salary interpretation
- remote geography
- AI leverage

must not be silently written into the core CanonicalJob model.

Derived records should preserve:

- input entity ID
- extractor name
- extractor version
- input hash
- created_at
- confidence
- extraction method

### Raw Observation Persistence

The in-memory RawJob model does not require a JobPosting ID at collection time because the corresponding durable JobPosting may not exist yet.

During persistence:

1. `(source_provider, source_scope, external_id)` is used to resolve or create the JobPosting.
2. The repository calculates a deterministic observation hash from source identity, source URL, and payload.
3. The first observation and each observation that differs from the immediately previous persisted observation are stored.
4. An immediately unchanged observation updates lifecycle state without duplicating JSON.
5. A later sequence such as A -> B -> A stores all three versions.
6. The RawJob observation is stored with a foreign-key relationship to its JobPosting.
7. The database must preserve the relationship:

   JobPosting 1 -> many RawJob observations.

This relationship is mandatory in persistent storage even though it is not required in the collector-facing RawJob model.

`latest_observation_hash` is an arrival-order cursor. It represents the most recently persisted observation, not necessarily the observation with the greatest `fetched_at`. Normalized JobPosting state and `last_seen_at` follow event-time freshness: a stale changed observation is preserved as raw provenance and becomes the latest arrived observation, but it must not regress the durable normalized state or `last_seen_at`.

### Persistence Serialization

The persistence boundary uses deterministic representations:

- aware datetimes are converted to UTC and stored as `YYYY-MM-DDTHH:MM:SS.ffffffZ`;
- Decimal values are stored as exact canonical strings without conversion through float;
- source payloads are stored as compact UTF-8 JSON with stable key ordering;
- NaN, infinity, and arbitrary non-JSON Python objects are rejected;
- SHA-256 hashes use exactly 64 lowercase hexadecimal characters.

`observation_hash` belongs to persistence and represents raw source identity, source URL, and payload. `content_hash` also belongs to persistence and represents the normalized source-level state stored on JobPosting.

### Repository Boundary

Application services depend on a small JobRepository protocol rather than SQLite. The repository owns durable IDs, lifecycle timestamps, deterministic hashes, raw-to-posting links, and atomic transaction behavior. Concrete SQLite or future PostgreSQL connections must not leak into collectors, normalizers, or user-facing interfaces.

---

## ADR-007: Product is designed for multiple users and interfaces

Date: 2026-08-17

Status: Accepted

### Decision

Job Market Analyzer is not designed as a one-off personal script.

The product should remain usable locally during the MVP stage, but its architecture must support future use by other people and future interfaces.

The core application logic must remain independent from:

- local filesystem paths;
- a specific operating system;
- CLI-only interaction;
- SQLite-specific implementation details;
- Telegram, Discord, web, or API interfaces.

The product may later expose the same core functionality through:

- CLI;
- REST API;
- web application;
- Telegram bot;
- Discord bot;
- scheduled background jobs.

The MVP does not require a multi-user SaaS architecture yet.

User accounts, authentication, permissions, billing, hosted infrastructure, and tenant isolation are explicitly postponed until they are justified by a real product requirement.

Configuration and secrets must remain external to source code so that different users and deployment environments can run the application safely.

Storage, collectors, analysis logic, and application services should be designed so that they can be reused by multiple interfaces without duplication.

---

## ADR-008: Source-observed tags are normalized intelligence inputs

Date: 2026-08-18

Status: Accepted

### Decision

`NormalizedJobPosting` and `JobPosting` contain `source_tags` as an immutable, deterministic tuple of source-observed labels.

Tag normalization:

- accepts only string elements from source arrays;
- trims and collapses whitespace;
- drops blank and exact duplicate values;
- preserves source spelling and case;
- sorts values deterministically;
- ignores malformed optional elements without discarding an otherwise valid vacancy.

Tags are stored as canonical JSON and participate in the normalized posting `content_hash`. Existing postings are migrated to the empty tuple and rehashed through the current normalized-state serializer.

### Boundaries

`source_tags` are not canonical skills, role classifications, translated labels, or alias-normalized technologies. Future deterministic analyzers may consume title, description, and `source_tags`, but must emit separate versioned derived records with evidence.

The original `RawJob.payload` remains the authoritative source observation and is not modified by tag normalization.

---

## ADR-009: Skill extraction starts with a versioned deterministic taxonomy

Date: 2026-08-18

Status: Accepted

### Decision

Skill taxonomy version `1` is an analyzer-curated immutable Python data structure. Taxonomy v1 is curated and intentionally incomplete. A pure extractor consumes normalized posting `title`, `description_text`, and `source_tags` and returns immutable structured `SkillEvidence`.

Every accepted alias has a stable rule ID. Matching uses Unicode-aware boundaries, punctuation-aware aliases, and explicit contextual guards for ambiguous terms. Output order and evidence deduplication are deterministic. The same canonical skill may produce at most one evidence record per input field so title, description, and tag provenance remain distinct. The single taxonomy/extractor version covers the full deterministic extraction semantics: aliases, boundaries, contextual guards, and match behavior. Any future change that alters those semantics must advance the version once derived output is persisted.

Each evidence record identifies:

- canonical skill code and display name;
- evidence field;
- matched alias;
- short evidence text;
- stable rule ID;
- exact or contextual match kind;
- mention kind.

The initial mention kind is `mentioned`. A mention must not be presented as proof that a skill is required, preferred, or essential. Absence of evidence means only that no current v1 rule matched; it is not proof that the vacancy does not mention or require the skill in reality.

### Boundaries

The extractor itself does not use AI, LLMs, embeddings, networking, or persistence. It does not infer unknown source tags or cloud-provider skills from related service names. An exact source-tag alias may bypass prose-only contextual guards because source tags are structured source observations, while unknown tags still produce no skill evidence. A separate persistence service may store the immutable extractor result; roles, companies, analytics, and confidence/requirement classification remain later checkpoints.

---

## ADR-010: Skill intelligence is versioned, derived, and recomputable

Date: 2026-08-18

Status: Accepted

### Decision

Skill evidence belongs to a persisted `JobPosting` but remains separate from authoritative source/domain state. SQLite stores:

- one global `skills` reference row per stable canonical skill code;
- one `analysis_runs` row per posting, analyzer kind, taxonomy version, extractor version, and analyzer input hash;
- at most one `job_skills` evidence row per analysis run, skill code, and evidence field, with an evidence-time `skill_name` snapshot.

The dedicated skill input hash contains only the actual deterministic extractor inputs: `title`, `description_text`, and normalized `source_tags`. `None`, empty, and whitespace-only descriptions use one canonical no-description representation. The hash excludes company, salary, location, URLs, lifecycle timestamps, raw observations, and persistence IDs. The current single semantics version is persisted as both taxonomy and extractor version, keeping the schema explicit without adding a second versioning subsystem.

A run is persisted even when extraction finds zero skills. Identical posting/version/input analysis reuses the existing run. Changed input or version creates a new run, and historical runs coexist. Source tables are never mutated by analysis, and migration does not automatically backfill intelligence.

The SQLite intelligence repository owns a short transaction covering the run, required skill reference rows, and all mention evidence. Any evidence failure rolls back the complete new run. Derived rows cascade from a deleted posting; no derived relationship may delete or block authoritative source data.

The global `skills` row preserves its first persisted display name; later runs with a different display label do not overwrite it. Historical evidence does not read that mutable reference label: `job_skills.skill_name` snapshots exactly what its extractor run produced. The skill-specific key rejects analyzer kinds other than `skills`.

Initialization rejects unsupported future schema versions before DDL, rejects partial intelligence structures in v1, and validates the critical declared-v2 structure. Derived DDL, structural validation, and the `user_version = 2` update share one transaction, so failure leaves committed v1 intact and retryable.

### Boundaries

The trusted internal analysis service expects its caller to provide the current persisted `JobPosting` state. A source-independent `JobPostingReader` contract now supports the bounded manual CLI by reconstructing current SQLite rows through persisted deserialization and domain validation. Future automatic orchestration must use that durable boundary rather than stale collector objects. The service does not analyze `RawJob`, perform collection, or schedule work. Persisted evidence still means only `mentioned`, never required, preferred, proficient, or employer-verified.

Future analytics may join `job_skills` through `analysis_runs` and `job_postings` to `canonical_job_id`, and should count distinct canonical jobs where appropriate. Complete cross-source canonical linking is not implemented, so those future counts cannot yet claim complete cross-source deduplication.

---

## ADR-011: Taxonomy v2 is a bounded real-data revision

Date: 2026-08-19

Status: Accepted

### Decision

Local validation used 100 persisted Remote OK postings and 100 persisted Web3.career postings. Taxonomy v1 runs remain immutable historical evidence. Changes to canonical skills, aliases, and contextual matching advance the single taxonomy/extractor semantics version to `2`; no second versioning mechanism is introduced.

V2 adds 13 locally observed canonical skills: Bash, Cosmos, CSS, EVM, Figma, Grafana, HTML, Apache Kafka, Linux, Prometheus, React Native, Snowflake, and Solana. Ambiguous bare mentions for Bash, Cosmos, Figma, Kafka, Prometheus, Snowflake, and Solana require explicit technical context in prose but remain exact direct evidence when supplied as a whole source tag. Safe compound aliases such as `Bash shell`, `Kafka Streams`, and `Snowflake warehouse` remain direct evidence. V2 keeps direct-mention semantics and does not infer parent, dependency, or requirement relationships.

Broad `Blockchain`, `Web3`, and `Bitcoin` terms are deliberately not added in this revision. They occurred frequently but often described the employer, industry, product, finance, marketing, or editorial context rather than a concrete skill. Higher raw coverage is not sufficient justification for accepting those false-positive risks.

### Consequences

The same unchanged posting input can have coexisting v1 and v2 `analysis_runs`. Repeating v2 reuses its run and evidence. Local posting-level coverage changed from 15% to 16% for Remote OK and from 62% to 67% for Web3.career; this is validation evidence, not complete market analytics or proof that v2 is universally better.

The two local databases were collected before normalized `source_tags` existed and migrated with empty tag tuples, so this validation cannot measure real source-tag recognition. The Remote OK sample also contains non-vacancy, placeholder, non-English, and apparently mismatched/boilerplate descriptions. Those data-quality limitations must remain visible in reporting rather than be hidden with source-specific extractor rules.

---

## ADR-012: Role Classification V1 is title-first and non-persistent

Date: 2026-08-21

Status: Accepted

### Decision

Role Classification V1 is a pure deterministic classifier with 19 stable role codes and immutable direct evidence. It evaluates title patterns first. Description fallback is allowed only when the title yields zero roles and only for an explicit role statement or header. Direct compound titles may emit several roles; otherwise no parent, sibling, seniority, or domain role is inferred. Zero evidence is the explicit Unknown result, not a synthetic taxonomy member.

Role, seniority, and domain remain independent analysis dimensions. Source tags are not an input to this role version. The implementation has no persistence, schema, service, CLI, source-specific, network, or AI dependency.

### Consequences

The same title and description always produce the same ordered evidence. Conservative rules accept lower coverage rather than fabricate a role from generic engineering, domain, or incidental description language. The English-oriented taxonomy and local 200-posting validation are bounded evidence, not complete market analytics.

Role persistence, input hashing, recomputation, and database migration require a later explicit decision after this pure contract is reviewed. Any future persisted semantics change must use a new version.

## ADR-013: Persist role classification as versioned derived intelligence

**Status:** Accepted and committed.

This decision supersedes ADR-012 only where it postponed persistence; the committed pure classifier semantics remain unchanged. Role Classification V1 remains a pure classifier, while a separate service and repository persist its immutable result. Roles reuse the generic `analysis_runs` identity `(job_posting_id, analyzer_kind, taxonomy_version, extractor_version, input_hash)` with `analyzer_kind = roles`. The current single semantics version is stored honestly as both taxonomy and extractor version. A dedicated role hash contains only `title` and `description_text`; absent, empty, and whitespace-only descriptions share one canonical absence representation.

Schema v3 adds `roles` and `job_roles` without rebuilding or backfilling source, skill, or existing analysis data. Unknown is a successful `analysis_runs` row with zero evidence rows. Role and skill evidence remain in separate tables, with database triggers enforcing their analyzer kind on insert and evidence reassignment. The five analysis-run identity fields are immutable after insertion, so existing evidence cannot be silently reinterpreted by changing its posting, analyzer kind, version, or input hash. The SQLite repository uses `BEGIN IMMEDIATE`, parameterized writes, the generic run uniqueness constraint as the concurrency source of truth, and one atomic transaction for the run, role references, and evidence.

`roles.code` is stable language-neutral identity. The global reference keeps its first persisted display name, avoiding recomputation-order label changes. `job_roles.role_name` is the historical presentation snapshot and retrieval never substitutes the current global label. Evidence also stores field, matched text, evidence snippet, rule ID, and match kind; taxonomy regexes and aliases remain code-owned.

The service accepts trusted current persisted `JobPosting` state. A stale supplied object can create a valid historical run for stale inputs, so automatic orchestration must reload current durable state first. Role persistence does not implement current/latest-run selection, role demand analytics, seniority, domain classification, salary, companies, or multilingual extraction.

---

## ADR-014: Manual role validation uses exact current-input runs

Date: 2026-08-21

Status: Accepted and committed.

### Decision

The manual `analyze-roles` CLI reads a bounded deterministic set of current durable `JobPosting` records and delegates every posting to `analyze_job_roles()`. Its statistics and samples use only the exact `analysis_run_id` returned or reused for the current role input hash and active version. It does not introduce a latest-by-time query or analyze `RawJob` observations.

Unknown is a successful persisted run with zero role evidence. Role counts are distinct-posting counts; evidence, Unknown, and multi-label output is deterministic and bounded. Systemic extraction, repository, initialization, and schema errors abort with a non-zero exit. An existing database path is mandatory so a typo cannot silently create an empty analysis database.

### Consequences

The command is a one-shot development and validation workflow, not scheduling or production orchestration. Repeated unchanged runs are idempotent, while changed title, description, or analyzer version creates a historical run. Output remains posting-level and cannot claim complete cross-source canonical deduplication. No network, token, raw payload, or full description is part of this workflow.

---

## ADR-015: Dashboard v0 analytics are read-only and posting-level

Date: 2026-08-21

Status: Accepted

### Decision

Add a separate `AnalyticsRepository` read boundary with immutable UI-independent
DTOs and a direct SQLite implementation. Dashboard v0 queries count current durable
`JobPosting` rows. They resolve current role and skill intelligence only by exact
analyzer kind, active taxonomy/extractor version, and the current analyzer input hash;
creation-time ordering is not current-state identity.

An exact run with evidence is `analyzed_with_results`, an exact run without evidence
is `analyzed_zero`, and absence of an exact run is `not_analyzed`. Aggregates count
distinct postings. List/search inputs are bounded and parameterized, and list DTOs do
not expose descriptions or raw source payloads.

### Alternatives rejected

- `MAX(created_at)` would silently select stale or incompatible history.
- Adding analytics methods to `JobRepository` would mix write persistence and product
  queries.
- Materialized analytics tables, schema v4, FTS, ORM, and a generic query framework
  are unnecessary at the measured local scale.
- Default canonical counts would imply deduplication that current cross-source linking
  cannot guarantee.

### Consequences

The first local API can map stable endpoints directly to the analytics contract.
Codes remain language-neutral while English labels are replaceable presentation data.
Salary, seniority, normalized geography, fuzzy linking, public HTTP, and frontend work
remain separate future milestones.

---

## ADR-016: Dashboard v0 uses a local read-only FastAPI adapter

Date: 2026-08-21

Status: Accepted and committed.

### Decision

Expose `AnalyticsRepository` through a minimal FastAPI application and the existing
`job-market-analyzer serve` CLI. The server requires an existing current-schema
SQLite path, binds `127.0.0.1:8000` by default, validates without migration, and opens
one `mode=ro` plus `query_only` connection per request. Explicit Pydantic response
models form the HTTP contract; API handlers do not reproduce analytics joins or
current-intelligence semantics.

The API contains only bounded GET routes for health, overview, jobs, role detail,
skill detail, and source summaries. Errors use stable codes, generic messages, and a
request ID. Development CORS allowlists only the two localhost port-3000 origins and
does not allow credentials.

### Alternatives rejected

- Flask would require more handwritten validation and OpenAPI plumbing for no MVP
  benefit.
- A generic REST/ORM layer would duplicate the committed query boundary.
- A global SQLite connection is unsafe across request threads.
- Opening SQLite normally could create a typo-path database or mutate journal/schema
  state, contradicting the read-only contract.
- Authentication, rate limiting, Redis, caching, cursor pagination, and hosted
  deployment are unnecessary for this bounded localhost-only sprint.

### Consequences

Dashboard v0 can consume a stable local JSON API immediately. FastAPI and minimal
Uvicorn are runtime dependencies; HTTPX2 is development-only for current TestClient
compatibility. OpenAPI remains enabled locally. Cross-source deduplication, frontend,
accounts, public exposure, and hosted concurrency remain future work.

---

## ADR-017: Dashboard v0 is a separate server-rendered Next.js consumer

Date: 2026-08-21

Status: Accepted for the current uncommitted implementation checkpoint.

### Decision

Place the browser application in `web/` with its own npm dependency boundary. Use
Next.js 16 App Router, React, TypeScript, server components, one small client
navigation component, native forms and URL query parameters, and hand-written CSS.
The frontend calls only the local read-only API through a typed client with a
five-second timeout and runtime response guards.

Add one compatible API query parameter, `GET /api/overview?top_limit=1..100`, so the
Jobs, Roles, and Skills screens can obtain all observed filter identities without
fetching every posting or duplicating backend taxonomies. The default remains 10.

### Alternatives rejected

- A client-side state framework adds lifecycle and synchronization work that URL
  state and server rendering already solve.
- A frontend proxy or duplicated Node API hides local configuration and adds another
  HTTP boundary without product value.
- Copying role and skill taxonomies into TypeScript would create drifting identities.
- Fetching every posting to discover filter options violates bounded list behavior.
- A chart or component library is unnecessary for summary cards, tables, and CSS
  coverage bars.

### Consequences

The Python package remains independently installable and the frontend has no access
to SQLite or collection credentials. Dashboard navigation is refresh-safe and
bookmarkable. Backend unavailability and invalid API responses are visible without
stack traces. Counts remain explicitly posting-level, skill text says mentioned or
co-mentioned rather than required, and source dates describe dataset freshness rather
than uptime. Salary, seniority, geography, canonical linking, accounts, deployment,
and saved user state remain postponed until personal-use evidence justifies them.

---

## ADR-018: Guided updates use explicit source and language-aware analyzer registries

Date: 2026-08-22

Status: Accepted and committed.

### Decision

Add a one-shot `job-market-analyzer update --database PATH` orchestration service.
Its static typed source registry contains only provider identity, display metadata,
the existing collector/normalizer composition, enablement, and optional credential
environment name. Its analyzer registry keys existing durable-posting runners by
analyzer kind and input language. Current registrations are `skills/en` and
`roles/en`; requesting `uk` is rejected before collection or database creation.

Sources execute sequentially in registry order. A missing source credential is an
explicit source skip. A collector/network failure is recorded and later sources
continue. Existing typed item failures remain recoverable collection results.
Unexpected normalization, repository, schema, transaction, and database failures are
systemic and abort. Analysis follows collection and reloads current persisted
postings. Non-database analyzer failures are reported independently; SQLite and
transaction-state failures abort. Any reported source item, source, or analyzer
failure gives the CLI a non-zero exit status even when useful work completed.

### Alternatives rejected

- Six new hardcoded CLI branches would make each source addition edit orchestration.
- A dynamic plugin framework, dependency injection container, queue, or scheduler is
  unnecessary for six local adapters.
- Inferring analyzer language from source would be inaccurate for mixed-language
  feeds.
- Treating missing Web3 credentials as a whole-command precondition would prevent
  useful credential-free collection.
- Silently routing `uk` to English rules would misrepresent extractor capability.

### Consequences

The default update creates or reuses SQLite, collects all enabled sources, runs all
current English analyzers, prints one posting-level summary, and leaves the database
ready for `serve`. Existing repository and analysis identities make unchanged repeat
runs idempotent. Adding a future source or `skills/uk` / `roles/uk` is a registry
composition change, not an orchestration rewrite. CLI display remains English and is
separate from analyzer input language. This decision adds no source, schema,
scheduler, automatic language detection, or Ukrainian taxonomy.

---

## ADR-019: Optional accounts arrive only after the hosted read-only alpha

Date: 2026-08-22

Status: Accepted.

### Decision

Anonymous read-only access remains the permanent baseline mode of the product.
Optional user accounts are introduced only after the hosted read-only alpha is
running and only for personal state: saved searches and filters, notes, a skill
profile, and later skill-gap recommendations. Personal data lives in a logically
separate schema from the global market dataset and never mutates core domain
models. The self-hosted/local mode keeps working without any account, using local
configuration or a local profile instead of hosted authentication.

### Reason

Personal value features (skill gap, one-click "what should I learn") depend on
trustworthy market evidence first: job lifecycle, seniority, geography, and salary
quality. Adding authentication earlier would build personalization on weak data
and contradict product honesty. Public read-only exposure also validates
infrastructure and gathers feedback without an auth burden.

### Consequences

Public GET endpoints stay unchanged; personal endpoints are additive (for example,
`/api/me/...`) over the same core. A future security sprint precedes any public
account handling. No authentication work happens before the hosted alpha exists.

---

## ADR-020: Retention uses lifecycle status, not deletion

Date: 2026-08-22

Status: Accepted; Job Lifecycle v1 is implemented as a read-time freshness
boundary (`ACTIVE_POSTING_WINDOW_DAYS = 30`, active-only defaults, explicit
`include_stale` history parameter). Persisted status columns and
source-provided expiry data remain future work.

### Decision

Old postings are not deleted or moved to a separate archive on a time schedule.
Instead, postings receive normalized lifecycle semantics (for example active,
stale, removed, expired) derived from source-aware observation history, and user-
facing views default to currently-active postings with explicit freshness filters.
Historical rows remain stored because they are required for provenance,
idempotency invariants, and future trend analytics.

### Reason

Source feeds expose only their current listing window; anything not collected when
published is lost forever, so broad collection plus durable retention is the only
viable model for both search and market analytics. Deleting stale rows would
destroy trend analytics and raw-provenance guarantees while saving negligible
storage at this scale. Freshness is a query/filter concern, not a physical
retention policy.

### Consequences

A dashboard must distinguish active from historical postings once lifecycle lands;
until then, counts remain honest posting-level totals without claiming everything
is currently open. Any future physical pruning must be an explicit, documented
policy decision that preserves raw observations.

---

## ADR-021: Role Taxonomy v2 is an evidence-driven real-dataset revision

Date: 2026-08-22

Status: Accepted and committed.

### Decision

After the first combined six-source plus Greenhouse dataset reached 2,871
postings, Unknown titles were mined systematically to ground a bounded role
taxonomy revision. The single taxonomy/extractor semantics version advances
from `1` to `2`; historical v1 runs remain preserved and exact-current
resolution automatically selects v2 by version plus input hash.

V2 additions, each tied to observed title families among the 1,926 Unknown
postings:

- sales_bd: account executive/manager, sales development representative,
  SDR/BDR acronyms, alliances leadership, head/vp/director of sales;
- support: bare support engineer, customer success manager/specialist family;
- security: SOC analyst, security specialist/architect/consultant/manager;
- devops_platform: GitOps engineer, cloud engineer, compound
  "site reliability / X engineer" titles;
- operations: operations specialist/analyst/coordinator/associate with
  domain-word negative lookbehinds so "Security Operations Analyst" stays
  security-only;
- finance: trust officer/administration family.

### Rejected

Generic "Software Engineer", "Software Developer", and "Web Developer" titles
(~300 postings) deliberately remain Unknown: without a functional-domain
signal they would fabricate a specific role and violate precision-first
semantics. Management titles (engineering manager, director) belong to a
future seniority dimension, not a functional role code. Inverted Greenhouse
title forms ("Engineer, Software") are noted but not solved this round.

### Consequences

Measured posting-level coverage on the live dataset rose from 32.9% to 45.6%
(1,310 classified). The largest gain is sales_bd (270 to 550 postings),
reflecting the previously invisible commercial side of the market. This is a
bounded validation measurement, not complete market analytics; cross-source
canonical deduplication still does not exist.

---

## ADR-022: Seniority v1 is a title-only, experience-axis analyzer

Date: 2026-08-22

Status: Accepted and committed.

### Decision

Add Seniority Classification V1 as the third deterministic intelligence
boundary, registered as `seniority/en` in the analyzer registry. It consumes
only `title`, applies a versioned seven-level experience taxonomy (intern,
junior, mid, senior, lead, staff, principal), and returns at most one evidence
record using highest-rank precedence. Zero evidence is Unknown. Persistence
reuses the generic `analysis_runs` identity with dedicated input hash over
`title` only; schema v4 additively adds `seniority_levels` and `job_seniority`
with analyzer-kind triggers, no backfill.

### Reason

After Role Taxonomy v2, the remaining Unknown population is dominated by
explicit experience markers (senior/staff/principal) that are orthogonal to
functional roles. Seniority was also the top-priority data-quality capability
in the handoff. Restricting v1 to title-only keeps the input hash stable under
description edits, since experience signals live in titles in practice.

### Rejected

People-management levels (manager, director, head of, VP) are deliberately not
seniority evidence in v1 because functional titles such as Product Manager or
Community Manager would produce false people-management classifications.
Bare "lead" is accepted only with engineering context for the same reason.
Generic engineering titles without experience signals remain Unknown.
Dashboard/API exposure is postponed until the analyzer accumulates real-dataset
validation, per the analyzer onboarding checklist.

### Consequences

First live pass over 2,871 postings classified 1,022 (35.6%): senior 781,
staff 151, principal 47, junior 22, intern 17, lead 4. The low junior/mid/lead
counts reflect conservative rules rather than market absence; future taxonomy
revisions may add guarded patterns with explicit version bumps.

---

## ADR-023: Geography v1 classifies arrangement and region eligibility

Date: 2026-08-22

Status: Accepted and committed.

### Decision

Add Geography Classification V1 as the fourth deterministic intelligence
boundary, registered as `geography/en`. It consumes normalized
`description_text`, `location_text`, and the structured `is_remote` flag;
titles are intentionally not an input so retitling does not invalidate runs.
It emits at most one work-arrangement evidence (`arrangement_remote`,
`arrangement_hybrid`, `arrangement_onsite`) plus multi-label region evidence
(`region_worldwide`, `region_europe`, `region_north_america`,
`region_latin_america`, `region_asia_pacific`). Schema v5 additively adds
`geography_terms` and `job_geography` with analyzer-kind triggers and no
backfill. The structured source flag is authoritative for the remote
arrangement when present.

### Reason

Remote eligibility is a top user filter and the third data-quality priority.
Lever and Ashby now supply structured workplace flags, while Greenhouse and
aggregators require guarded text rules; the analyzer unifies both into one
versioned, recomputable contract. "Anywhere" style worldwide claims are guarded
against scoped places ("anywhere in the US"), and bare hyphenless "hybrid" is
ignored to avoid hybrid-cloud false positives.

### Rejected

Country-level eligibility, timezone constraints, and visa requirements remain
future revisions: current feeds rarely expose them reliably and conservative
region buckets avoid fabricating precision. Dashboard/API exposure is postponed
until the analyzer accumulates real-dataset validation.

### Consequences

First live pass over 5,548 postings classified 4,780 (86.2%):
3,165 remote, 287 onsite, 125 hybrid arrangements; regions: North America 3,065,
worldwide 808, Europe 772, Asia Pacific 327, Latin America 67. Region counts are
multi-label and must not be presented as exclusive partitions.

---

## ADR-024: Salary v1 normalizes structured and text salaries conservatively

Date: 2026-08-23

Status: Accepted and committed.

### Decision

Add Salary Classification V1 as the fifth deterministic intelligence boundary,
registered as `salary/en`. It consumes only the normalized salary fields
(`salary_text`, `salary_min`, `salary_max`, `salary_currency`,
`salary_period`) so unrelated posting edits do not invalidate runs. Two
provenance paths exist: `structured` values pass through with `direct`
confidence, and guarded text parsing (`parsed` confidence) handles common
English formats including k-notation, ranges, "up to", currency symbols and
ISO codes. Annual equivalents are derived only under a known period using
explicit conventions (2080 hours, 260 days, 52 weeks, 12 months); unknown
period stores bounds with null annual figures. Equity/token-only mentions
produce no estimate; inverted ranges are rejected rather than swapped.
Schema v6 additively adds `job_salaries` keyed by analysis run with
analyzer-kind triggers and no backfill.

### Reason

Salary was the last top-priority data-quality dimension. The conservative
guards implement the documented product honesty rules: no blind conversion
without period context, no invented currencies, no silent range swaps.

### Consequences

The first live pass estimated 104 of 5,548 postings (92 structured, 12 text;
94 USD, plus EUR/CAD/GBP/PLN). Coverage is thin because the large ATS sources
do not publish compensation through these endpoints (the Ashby adapter
deliberately requests without compensation fields); enabling Ashby
compensation and mining Greenhouse description text are explicit future
revisions requiring their own versioning decisions. Median annual minimums by
currency are now computable but remain posting-level observations, not market
certified statistics.

---

## ADR-025: Skill Gap v1 is a read-only deterministic calculator

Date: 2026-08-23

Status: Accepted and committed.

### Decision

Add Skill Gap V1 as a pure read-only calculator over ``AnalyticsRepository``:
given a target role code and a list of skills the user claims (matched
case-insensitively against canonical taxonomy codes and display names), the
service ranks the role's market-mentioned skills by posting frequency and
splits them into gaps and matches. Unrecognized inputs are reported back, not
dropped or invented. No persistence, no user profiles, no authentication, no
AI: the first CLI entry point is ``skill-gap --role CODE --skills a,b,c``.
Every row is mention-level evidence ("mentioned in N of M active postings for
this role") and is never presented as an employer requirement.

### Reason

This is the first product surface of the mission chain (market evidence >
personal gap). It became honest only after lifecycle, roles v2, seniority,
geography, and salary landed: ranking by stale or unclassified data would have
misled users. Deferring persistence keeps privacy surface zero until hosted
accounts exist (ADR-019).

### Rejected

Weighted scoring beyond mention counts, seniority-aware filtering inside the
calculator, and any LLM explanation are postponed; they require evaluation
datasets (handoff #59) before recommendations can be trusted.

### Consequences

A future web UI can reuse the same pure function over the API without new
storage. The report inherits all dataset caveats: posting-level counts,
taxonomy coverage limits, and English-language sources.

---

## ADR-026: Ashby structured compensation is enabled

Date: 2026-08-23

Status: Accepted and committed. Amends ADR-024's "future revisions" note.

### Decision

The Ashby collector requests `includeCompensation=true`. The normalizer reads
the first structured `Salary` component from
`compensation.summaryComponents` (bounds, ISO currency, interval mapped to a
period) directly into normalized salary fields; equity-only or malformed
structures yield no salary rather than failing the posting. This replaces the
ADR-024 paragraph deferring "enabling Ashby compensation" to future work.

### Reason

Ashby exposes exactly the structured provenance our salary contract wants —
no text parsing and no invented numbers — so enabling it required no new
versioning subsystem: the existing `salary/en` input hash already covers these
normalized fields, and re-collection naturally created fresh versioned runs.
Live effect: salary coverage rose from 104 to 1,324+ postings.

### Consequences

Salary data now skews toward AI-era companies that publish bands (USD-heavy,
high medians); dashboards must keep presenting per-currency medians as
posting-level observations, not market statistics.

---

## ADR-027: Skill Taxonomy v3 adds the marketing and communications family

Date: 2026-08-23

Status: Accepted and committed.

### Decision

Add 26 canonical marketing/growth/communications skills to the taxonomy
(positioning, go-to-market, brand marketing, campaign management, marketing
funnel, marketing strategy, growth marketing, B2B marketing, copywriting,
CRM, social media marketing, content marketing, paid media, performance
marketing, SEO, public relations, influencer marketing, market research,
A/B testing, Google Ads, Google Analytics, digital marketing, lead
generation, community management, marketing analytics, Canva), grounded in a frequency-mining pass over 216 live marketing_growth
postings. The single taxonomy/extractor version advances to `3`; v2 runs
remain preserved and exact-current resolution selects v3 automatically.

### Reason

The first real user pass over the Skill Gap page exposed a coverage blind
spot: the marketing role showed DeFi/AWS/SQL as "top skills" because the
taxonomy had zero marketing-domain entries. Mining showed 39 frequent
marketing phrases, all missing. Ambiguous bare words (brand, PR, GTM) are
deliberately excluded or guarded (PR strategy, GTM strategy only) to avoid
pull-request and Google-Tag-Manager false positives. Email marketing was
identified by mining but deferred to the next revision (dropped from the
shipped v3 set during curation).

### Consequences

Live re-analysis of 7,413 postings: 15,044 evidence records created;
marketing gap now leads with Positioning (45.4%) and Go-to-Market (44.4%).
The same mining approach should be repeated per role family before further
taxonomy revisions.

---

## ADR-028: Skill Taxonomy v4 covers all role families from cross-family mining

Date: 2026-08-23

Status: Accepted and committed.

### Decision

Extend the taxonomy to 122 canonical skills (+36) after running the same
frequency-mining pass across ALL 19 role families (not just marketing).
Additions span: AI/ML (machine learning, LLM, generative AI, prompt
engineering, fine-tuning, deep learning), data (Spark, dbt, Airflow, ETL,
data modeling, BigQuery, data analysis, Excel), design (prototyping, product
design, design systems, user research), product (product strategy),
go-to-market (prospecting, forecasting, negotiation, enterprise sales,
customer success, account management, sales operations), support
(troubleshooting, Zendesk), finance (financial reporting, budgeting), and
security/compliance (incident response, vulnerability management,
penetration testing, OWASP, SIEM, AML). The single
taxonomy/extractor version advances to `4` (amended same day to `5` after
contextual-guard hardening of Excel/Spark/Positioning/Airflow/ML aliases — the
guarded semantics required a fresh version once v4 runs had been persisted).

### Reason

The marketing-only v3 revision fixed one family but left identical blind
spots in every other role. Cross-family mining exposed two classes of
phrases: genuine skills (added) and context words appearing everywhere as
company-topic boilerplate (compliance, HR, recruitment, roadmap,
onboarding, documentation) — the latter are deliberately excluded because
they describe what the employer talks about, not what the candidate must
know.

### Consequences

Live re-analysis of 7,413 postings: postings with at least one skill rose
from 4,969 (67%) to 6,442 (87%); zero-skill runs fell from 2,444 to 971.
Sales gaps now lead with Customer Success (30%), Negotiation (28%),
Prospecting (22%). The mining script pattern (candidate phrases per family,
threshold ?5 postings, taxonomy-status check) is the standing recipe for
future revisions.

---

## ADR-029: Source update run history and production update worker

Date: 2026-08-25

Status: Accepted.

### Decision

Persist one row per source update attempt in a new additive schema v7 table
`source_update_runs` (status `completed`/`failed`/`skipped`, redacted message,
fetched/persisted/failed counts, UTC start/finish). The guided update
orchestrator records every attempt; history is append-only, never upserted.
Analytics expose, per provider: last attempt status/time and last successful
update time through `/api/sources` and the Sources page. Production refresh
uses a dedicated compose overlay (`docker-compose.worker.yml`) that runs the
same image's `update` command against the server database with read-write
access, triggered by a systemd timer (`deploy/systemd/jma-update.*`).
Credentials flow from `.env`; a missing optional credential skips exactly its
own source exactly as before.

### Reason

The live site served a frozen snapshot under the 30-day freshness rule
(R3, DEPLOYMENT_STATUS). Source health was previously invisible: nothing in
the database distinguished "collected an hour ago" from "collected two weeks
ago" per provider. Recording attempts (not just successes) keeps failures and
credential skips observable without shell access.

### Consequences

Schema advances to v7 with a purely additive migration; repeated updates now
append history rows by design (this does not violate posting/observation/
analysis idempotency, which is unchanged). During a worker run the API may
serve the last WAL checkpoint for a few minutes because the container mounts
only the main database file; clean worker shutdown checkpoints everything.
The API requires a v7 database for `/api/sources`; deploy flow must run the
updater (or one manual update) after pulling new code.

---

## ADR-030: Role Taxonomy v3 adds delivery engineering, solutions architecture, and mined family extensions

Date: 2026-08-25

Status: Accepted.

### Decision

Mine the current 10,451-posting dataset for Unknown titles (exact-current v2
resolution) and land a bounded v3 revision: two new role codes plus targeted
rule extensions. `delivery_engineering` covers the Forward Deployed Engineer /
Deployment Strategist / Implementation Consultant / Professional Services
consultant family (330 postings matched). `solutions_architect` covers
Solutions Architect variants including delivery/senior/staff prefixes and the
inverted "Architect, Solutions" form (285 postings). Extensions: brand/graphic/
motion designer into design; database reliability engineer into
devops_platform; commercial counsel into legal_compliance; events roles into
marketing_growth; executive/administrative assistant into operations;
partnerships associate/specialist, sales-development leadership, and explicit
sales/deal operations into sales_bd; AI product engineer into ai_ml. The
taxonomy advances to version `3` (21 codes); historical v1/v2 runs remain and
exact-current resolution selects v3 automatically.

### Rejected

Bare level-titled engineers ("Senior Software Engineer", ~60 postings),
Technical Program Managers, bare "Product Engineer", and "IT Engineer" remain
Unknown - no functional signal without fabrication risk (extends the ADR-021
rejection list). Explicit "Solutions Engineer(ing)" stays in sales_bd as
pre-sales; it must not leak into solutions_architect or delivery_engineering,
now pinned by gold-set guard cases.

### Consequences

Same-dataset posting-level coverage rose from 40.5% to 47.7% (+750 classified).
A permanent gold-set FP/FN suite (tests/unit/test_role_taxonomy_gold_set.py)
now gates every future revision: positive, negative, and guard cases per
ambiguous alias, a pinned-version meta-test, and a coverage assertion that
every role code keeps at least one positive case (closes audit recommendation
R2 for roles). ESCO/O*NET cross-reference extended in
docs/TAXONOMY_VALIDATION.md.

---

## ADR-031: Skill Taxonomy v6 closes the last ESCO/O*NET gaps

Date: 2026-08-25

Status: Accepted.

### Decision

Add three canonical skills flagged as missing by the v5 ESCO/O*NET
cross-reference: `nlp` (full phrase plus a case-sensitive "NLP" acronym alias,
so lowercase prose like "we call it nlp" stays silent), `nginx`, and
`email_marketing` ("Email marketing", "Email campaigns"; bare "email" and
"campaigns" remain silent). The taxonomy advances to version `6`
(125 skills); historical runs are preserved and exact-current resolution
selects v6 automatically. Word-boundary compile semantics are reused; no new
context-rule machinery was required.

### Reason

The v5 validation report scheduled exactly these three additions. Closing
them brings expected-skill coverage across the 13 validated role anchors to
79/79 (100%), deepening evidence quality rather than chasing coverage
percentage.

### Consequences

Live-dataset posting-level skill coverage is unchanged at 84.6% by design:
133 postings gained at least one new canonical evidence record
(nlp 92, nginx 23, email_marketing 18), improving role-skill analytics
granularity. v6 gold cases with positive and false-positive guards are pinned
in tests/unit/test_skill_extraction.py alongside the existing guard suites.
