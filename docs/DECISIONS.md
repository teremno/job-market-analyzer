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
