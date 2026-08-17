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
2. The RawJob observation is then stored with a foreign-key relationship to that JobPosting.
3. The database must preserve the relationship:

   JobPosting 1 -> many RawJob observations.

This relationship is mandatory in persistent storage even though it is not required in the collector-facing RawJob model.