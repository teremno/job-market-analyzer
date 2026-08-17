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