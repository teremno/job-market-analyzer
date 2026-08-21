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
└─ RoleEvidence → pure result only; not persisted yet
↓
Later canonical-job analytics

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

Replaceable skill intelligence is stored separately in:

- `skills`, a small stable-code reference table;
- `analysis_runs`, one row per posting, analyzer/version, and dedicated input hash;
- `job_skills`, direct mention evidence owned by one analysis run, including the
  evidence-time skill display-name snapshot.

`SkillIntelligenceRepository` is separate from `JobRepository`. One analysis run, any required skill reference rows, and all `job_skills` evidence are committed atomically. Derived rows may cascade when their `JobPosting` is deleted; source/domain rows never depend on derived intelligence.

SQLite initialization reads `PRAGMA user_version` before application DDL. Versions newer than the supported schema fail without mutation. Committed v1 is structurally validated before the additive v2 migration, unexpected partial intelligence tables are rejected, and an existing v2 database must pass critical table, column, key, index, constraint, and foreign-key checks instead of being silently repaired.

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

Role Classification V1 is a second pure intelligence boundary. It consumes only `title` and optional `description_text`, applies a versioned 19-role taxonomy, and returns immutable direct `RoleEvidence`. Title evidence has precedence; an explicit description role statement is consulted only when the title produces no role. Zero evidence represents Unknown, and directly supported compound titles may produce several roles. Role, seniority, and domain remain separate dimensions.

The role classifier has no persistence, schema, repository, service, CLI, source-specific, network, AI, or `source_tags` dependency. Persisted role analysis, input hashing, and recomputation are deliberately postponed until the pure semantics have been reviewed. Later derived records may also cover seniority, salary interpretation, remote geography, and AI-assisted work potential.

Canonical analytics remove duplication only when multiple postings already share one `CanonicalJob`. Complete cross-source canonical linking is not implemented yet, so current data must not be described as fully deduplicated across sources.

## Engineering Principles

- Keep collectors independent from normalization, persistence, and analysis.
- Preserve original source payloads and trace every CanonicalJob back to its postings and observations.
- Keep application services independent from CLI, web, bots, and a concrete database.
- Prefer small, explicit modules and deterministic data transformations.
- Document external-source attribution in `docs/SOURCES.md`.
