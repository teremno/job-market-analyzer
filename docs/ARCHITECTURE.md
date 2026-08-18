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
Later structured extraction and analytics

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

The SQLite schema stores exactly three MVP tables:

- `canonical_jobs`;
- `job_postings`;
- `raw_jobs`.

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

Later deterministic analyzers may use the normalized posting title, description, and source-observed tags as inputs. `source_tags` must not be treated as extracted skills without taxonomy matching and evidence. Later derived records may cover skills, seniority, role classification, salary interpretation, remote geography, and AI-assisted work potential. Derived data must retain its input entity, extractor identity/version, input hash, creation time, method, and confidence instead of silently modifying CanonicalJob.

Canonical analytics remove duplication only when multiple postings already share one `CanonicalJob`. Complete cross-source canonical linking is not implemented yet, so current data must not be described as fully deduplicated across sources.

## Engineering Principles

- Keep collectors independent from normalization, persistence, and analysis.
- Preserve original source payloads and trace every CanonicalJob back to its postings and observations.
- Keep application services independent from CLI, web, bots, and a concrete database.
- Prefer small, explicit modules and deterministic data transformations.
- Document external-source attribution in `docs/SOURCES.md`.
