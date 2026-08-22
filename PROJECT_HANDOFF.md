# PROJECT_HANDOFF.md

## 0. Purpose of this document

This file is the primary handoff document for the `job-market-analyzer` project.

It is written so that a new coding agent or engineer can open the repository, read this file first, inspect the implementation and tests, and continue development without relying on prior chat history.

The codebase is the ultimate source of truth. If this document and the implementation ever disagree, verify the behavior against tests, migrations, repository contracts, CLI behavior, and current code before changing anything.

---

# 1. Product mission

Build an open, global career-intelligence platform that turns real job-market data into actionable guidance for people anywhere in the world.

The product should help a user answer:

- What jobs are available?
- Which roles are growing?
- Which skills employers actually demand?
- Which skills am I missing?
- What should I learn next?
- Which AI tools can make me more productive or employable?
- What should I build for my portfolio?
- Which jobs should I realistically target?
- How should I adapt my learning path to current market demand?

The long-term product is intended to be usable through:

- a public website;
- a self-hosted open-source deployment;
- a REST API;
- a Telegram bot;
- a WhatsApp bot;
- potentially a Discord bot;
- the existing CLI;
- future third-party integrations.

The project must remain useful even without a hosted SaaS product.

A technically capable user should eventually be able to clone the repository, provide required credentials/API keys, start the application, and use it locally or on their own server.

---

# 2. Core product philosophy

The project is not primarily a “job scraper.”

The project is a career-intelligence system.

Collection is only the first stage.

The complete intended value chain is:

```text
Global job sources
        ↓
Collection
        ↓
Normalization
        ↓
Durable job dataset
        ↓
Role / skill / salary / geography / seniority intelligence
        ↓
Market analytics
        ↓
User profile
        ↓
Skill gap
        ↓
Learning recommendations
        ↓
AI leverage recommendations
        ↓
Portfolio recommendations
        ↓
Job targeting
        ↓
Explanation in the user’s preferred language
```

The system should be evidence-driven.

Where possible:

- deterministic code should produce facts;
- structured market data should drive recommendations;
- AI should explain, synthesize, translate, and personalize;
- AI should not invent market facts that the database does not support.

A useful internal principle is:

> AI explains. Evidence decides.

---

# 3. Product priorities

## 3.1 Primary priority: global English-first core

The canonical product and engineering language is English.

Priority order:

1. Global sources.
2. English-language job-market data.
3. Stable normalized data.
4. High-quality role/skill intelligence.
5. Market analytics.
6. Geography, seniority, salary, job lifecycle, canonical deduplication.
7. User profile and skill gap.
8. Recommendations.
9. AI explanation layer.
10. Multilingual user experience.
11. Hosted website.
12. Bots and additional interfaces.
13. Local-market source expansion by country/region.

The system should not become country-specific too early.

The initial core should understand the broad international and remote job market before adding narrow local-market integrations.

---

# 4. Internationalization strategy

Internationalization is a product goal, but the architecture must distinguish several concepts.

## 4.1 Canonical internal language

The following should remain English or language-neutral:

- source provider codes;
- database field names;
- API contracts;
- role codes;
- skill codes;
- internal taxonomy identifiers;
- developer documentation;
- code;
- internal service names.

Examples:

```text
role_code = backend
skill_code = python
skill_code = docker
```

These should not become:

```text
backend_uk
python_de
docker_hi
```

Language affects detection and presentation, not canonical identity.

## 4.2 Separate these concepts

Do not conflate:

1. UI language
2. User conversation language
3. Vacancy/content language
4. Analyzer language
5. User location
6. Job geography
7. Job eligibility

A user may be located in Germany, use Ukrainian UI, search English-language remote jobs, and target Europe.

A user in India may use English UI, search worldwide remote jobs, and also include local Indian jobs.

## 4.3 Near-term multilingual strategy

The product core remains English-first.

The preferred near-term multilingual path is:

```text
English job data
        ↓
English / language-neutral structured intelligence
        ↓
multilingual explanation layer
```

This is more important initially than building separate full taxonomies for many languages.

Examples of future output languages:

- English
- Ukrainian
- German
- Hindi
- Urdu
- Dutch
- French
- Spanish
- Portuguese
- others as demand appears

## 4.4 Analyzer registry seam

The guided update architecture already supports analyzer registration by `kind + language`.

Current registry:

```text
skills/en
roles/en
```

Ukrainian intelligence is not implemented yet.

The command should not pretend otherwise.

A future implementation may register:

```text
skills/uk
roles/uk
```

without changing orchestration.

However, because the global source strategy is English-first, multilingual output may be implemented before broad multilingual vacancy analysis.

---

# 5. Open-source and hosted product model

The project should support two legitimate modes.

## 5.1 Self-hosted / local mode

Target audience:

- developers;
- advanced users;
- open-source contributors;
- people who want private local career intelligence;
- people who want to customize sources, filters, taxonomies, or recommendations.

Expected future quick start:

```text
git clone
configure environment
docker compose up
```

A native Python + Node development setup should remain available.

SQLite remains appropriate for simple local use.

## 5.2 Hosted product

The hosted product will eventually run under a public domain and support normal users without local setup.

Likely architecture:

```text
Internet
   ↓
Domain / DNS
   ↓
Reverse proxy
   ↓
Frontend
API
Worker/update process
PostgreSQL
```

Later:

```text
                    Web
                     │
Telegram ─────────── API ─────────── WhatsApp
                     │
                  Discord
                     │
                    CLI
```

All clients must rely on the same core application and API.

Do not create separate business logic for each bot.

---

# 6. Cost philosophy

Infrastructure and AI costs matter.

Prefer:

- low-cost VPS infrastructure;
- open-source components;
- inexpensive APIs;
- replaceable AI providers;
- deterministic computation where practical;
- caching and structured analysis before LLM calls;
- no unnecessary managed-cloud complexity.

Do not introduce Kubernetes, service meshes, distributed microservices, or expensive managed infrastructure without demonstrated need.

The early hosted product should be deployable on a reasonably small Linux VPS.

Likely initial category:

- 2–4 vCPU
- 4–8 GB RAM
- SSD/NVMe storage

This is not a final capacity recommendation. Benchmark before purchase.

---

# 7. Repository / package identity

Current technical repository/package name:

```text
job-market-analyzer
```

A possible future product/brand name discussed:

```text
SkillSignal
```

Do not rename the package or repository casually.

A product branding decision can be made later.

The repository name is currently a technical name and does not block product development.

---

# 8. Current high-level architecture

The core ingestion pipeline is:

```text
source
  ↓
collector
  ↓
RawJob
  ↓
source-specific normalizer
  ↓
NormalizedJobPosting
  ↓
generic collection service
  ↓
JobRepository / persistence
  ↓
durable JobPosting
  ↓
CanonicalJob
```

Current analytics are posting-level.

Cross-source canonical linking is NOT implemented.

Do not describe current counts as globally deduplicated unique jobs.

Use honest language such as:

```text
source postings
```

rather than:

```text
unique jobs worldwide
```

---

# 9. Current sources

Six sources are currently implemented and have been live-validated:

1. Remote OK
2. Web3.career
3. Himalayas
4. Jobicy
5. Remotive
6. We Work Remotely RSS

The project MUST NOT stop at these six sources.

These are the first working source set, not the final market universe.

Future expansion should continue.

Strong next source category:

- Greenhouse-hosted company job boards
- Lever-hosted company job boards
- Ashby-hosted company job boards

These ATS integrations are strategically valuable because they provide access to many companies without depending only on aggregators.

Other sources may be added later when they provide good value, stable access, and acceptable legal/technical behavior.

Some future sources may require:

- API keys;
- OAuth;
- RSS;
- public APIs;
- structured public endpoints;
- HTML scraping;
- curated company scopes.

Credential requirements must be explicit.

Never expose or log secrets.

---

# 10. Source expansion architecture

A guided source registry now exists.

The intent is that adding a source should not require rewriting orchestration.

Typical future source addition:

1. Add collector under:

```text
src/job_market_analyzer/collectors/
```

2. Add source normalizer under:

```text
src/job_market_analyzer/normalization/
```

3. Register one `SourceAdapter` in:

```text
src/job_market_analyzer/services/update_registry.py
```

Do not build a giant plugin framework unless the product actually requires one.

A typed static registry is currently preferred.

---

# 11. Source identity rules

Posting/source identity is:

```text
(source_provider, source_scope, external_id)
```

Normalization rules:

- `source_provider`: lowercase
- `source_scope`: lowercase
- `external_id`: preserve native identifier/case

Do not casually change this identity contract.

It affects idempotency and persistence semantics.

---

# 12. Raw observation / freshness semantics

Important persistence invariants exist around raw observations.

Raw observations preserve arrival history.

The latest observation hash means:

> the immediately prior arrival observation

It does NOT mean:

> the observation having the greatest fetched timestamp.

Example:

```text
A → B → A
```

must preserve all three raw versions.

Current normalized state follows event-time freshness.

A stale/out-of-order raw observation should still be persisted but must not roll back newer durable normalized state.

Do not replace these rules with naive “latest timestamp wins” logic without understanding existing tests.

---

# 13. Hashing and normalization

Current architecture intentionally distinguishes several hashes and input identities.

Important rule:

`source_tags` are normalized deterministically.

They are included in:

- skill input hash;
- content hash.

They are not included in:

- raw observation hash.

Hashing behavior is a critical invariant.

Before changing serialization, normalization, or hash inputs, inspect current tests and migration implications.

---

# 14. SQLite persistence conventions

Current persistence uses SQLite with deliberate safety choices.

Important conventions include:

- UTC exact timestamps;
- Decimal values stored as TEXT where applicable;
- canonical JSON serialization;
- UUID stored as TEXT;
- foreign keys enabled;
- WAL mode;
- `busy_timeout=5000`;
- caller-owned connections;
- `BEGIN IMMEDIATE` for write concurrency;
- no `INSERT OR REPLACE` shortcuts.

A real two-connection concurrency test exists.

It verifies that a waiting writer completes and both writes survive.

Do not weaken transaction semantics.

---

# 15. Skill Intelligence v2

Skill extraction is deterministic.

Current taxonomy:

- 60 canonical skills.

Main extraction contract:

```python
extract_skills(
    title,
    description_text,
    source_tags
) -> tuple[SkillEvidence, ...]
```

Persistence is versioned.

Relevant entities include:

- `analysis_runs`
- `skills`
- `job_skills`

Current analysis identity uses:

- title
- description
- source tags
- active analyzer version

A posting with no detected skill is still represented as an analysis run with zero evidence.

This distinction is important because:

```text
not analyzed
```

and:

```text
analyzed, no skill found
```

are different states.

Manual CLI exists:

```text
job-market-analyzer analyze-skills --database ... --limit N
```

Historical analyzer versions are intentionally retained.

Do not delete old analysis history as part of ordinary updates.

---

# 16. Role Classification v1

Role extraction is deterministic.

Current role codes:

1. ai_ml
2. backend
3. blockchain_protocol
4. community
5. data
6. design
7. devops_platform
8. finance
9. frontend
10. full_stack
11. legal_compliance
12. marketing_growth
13. mobile
14. operations
15. product
16. qa
17. sales_bd
18. security
19. support

Main extraction behavior:

```python
extract_roles(title, description_text)
```

Principles:

- title-first;
- description fallback;
- precision-first;
- direct multilabel only;
- empty result means Unknown.

Versioned persistence includes:

- `roles`
- `job_roles`
- analyzer-kind isolation

Exact-current analysis resolution must use:

```text
current input hash + active analyzer version
```

Do NOT replace this with:

```text
MAX(created_at)
```

Historical runs must not pollute current analytics.

Manual CLI:

```text
job-market-analyzer analyze-roles
```

---

# 17. Analytics layer

A read-only analytics abstraction is implemented.

Core interface:

```text
AnalyticsRepository
```

with SQLite implementation.

Current DTOs include:

- AnalyticsOverview
- PostingSearchFilters
- PostingListItem
- PagedPostings
- RoleDetail
- SkillDetail
- SourceSummary
- count DTOs
- AnalysisStatus

Current query capabilities include:

- overview
- job listing / filtering / search
- role detail
- top skills per role
- skill detail
- skill co-occurrence
- source summaries

Analytics use posting-level `DISTINCT` semantics.

Historical role/skill runs must not count as current.

---

# 18. API

FastAPI is implemented.

The local server command is:

```text
job-market-analyzer serve --database .\job-market.sqlite3
```

Default binding:

```text
127.0.0.1:8000
```

Current API endpoints:

```text
GET /api/health
GET /api/overview
GET /api/jobs
GET /api/roles/{role_code}
GET /api/skills/{skill_code}
GET /api/sources
```

Overview supports `top_limit`.

The jobs endpoint supports parameters such as:

- limit
- offset
- source
- role
- skill
- q

API behavior includes:

- read-only SQLite connections;
- explicit response models;
- stable error envelope;
- request ID;
- restricted local CORS;
- OpenAPI.

Current error contract resembles:

```json
{
  "error": {
    "code": "...",
    "message": "..."
  },
  "request_id": "..."
}
```

Do not casually break API contracts if frontend or future clients rely on them.

---

# 19. Dashboard v0

Frontend stack:

- Next.js 16.3.2
- React 19.2.8
- TypeScript 5.9.3
- App Router

Location:

```text
web/
```

Current pages:

- Overview
- Jobs
- Roles
- Role detail
- Skills
- Skill detail
- Sources

The dashboard is currently server-rendered/read-only.

Jobs support URL state for:

- query
- source
- role
- skill
- pagination

The API client:

- defaults to `http://127.0.0.1:8000`;
- supports `NEXT_PUBLIC_API_BASE_URL`;
- uses a 5-second timeout;
- uses `no-store`;
- performs runtime validation.

The dashboard has already been run successfully against a real local database.

---

# 20. Guided Update Flow

A major productivity milestone is complete.

Primary command:

```text
job-market-analyzer update --database .\job-market.sqlite3
```

It orchestrates:

1. all enabled sources;
2. persistence;
3. skill analysis;
4. role analysis;
5. summary output.

Current collection order:

```text
Remote OK
Web3.career
Himalayas
Jobicy
Remotive
We Work Remotely
```

Current analysis order:

```text
skills
roles
```

The update system is registry-driven.

It should remain extensible as more sources and analyzers are added.

---

# 21. Guided update source registry

The current source registry contains metadata such as:

- provider code;
- display name;
- collector factory;
- normalizer;
- enablement;
- optional credential environment variable.

Do not replace the registry with a hardcoded orchestration chain.

The entire purpose is that future sources can be registered without rewriting `update`.

---

# 22. Guided update analyzer registry

Analyzer registry keys use:

```text
kind + language
```

Current:

```text
skills/en
roles/en
```

This is an intentional extension seam for future analysis kinds and languages.

Future possibilities:

```text
seniority/en
salary/en
geography/en
skills/uk
roles/uk
```

Do not redesign this into an overly generic framework unless a concrete need arises.

---

# 23. Guided update credentials

Web3.career requires:

```text
WEB3_CAREER_API_TOKEN
```

Current behavior when missing:

- skip only Web3.career;
- continue credential-free sources;
- clearly report the skip;
- never print the token.

This is desirable for daily use.

A missing optional source credential is not a systemic application failure.

Credential values must be redacted from errors.

---

# 24. Guided update failure policy

The current update flow distinguishes:

## Source failure

Examples:

- network failure;
- malformed remote response;
- individual collector failure.

Behavior:

- record failure in summary;
- continue independent sources;
- analyze successfully persisted data;
- final exit code indicates partial failure.

## Analysis failure

Skills/roles analysis failure is reported separately.

## Systemic failure

Examples:

- incompatible schema;
- SQLite failure;
- repository failure;
- transaction failure;
- unexpected persistence-path failure.

Behavior:

- abort update.

Do not swallow systemic failures.

---

# 25. Guided update idempotency

Repeated unchanged update runs should not create duplicate:

- postings;
- raw observations;
- skill runs;
- role runs.

This has orchestration-level test coverage.

Idempotency is a fundamental product property.

---

# 26. Current test/quality state

Latest guided update sprint report:

- Python 3.13.7
- 731 tests passed
- Ruff: all checks passed
- `git diff --check`: clean
- frontend not changed in that sprint

Before that, an independent project audit rated the repository:

> READY FOR CONTINUED PRODUCT DEVELOPMENT

The audit found no blockers/high-severity architecture problems.

Do not assume this means the project is production-ready.

It means the foundation is healthy enough to continue.

---

# 27. Important historical hardening

Recent audit hardening included:

- Ruff version range constrained for reproducibility;
- generated `*.egg-info` removed from version control;
- `.gitignore` improved;
- unused/dead files removed;
- roadmap updated;
- frontend runtime validation tests added;
- real SQLite concurrency coverage added;
- wording corrected to avoid overclaiming uniqueness;
- disabled pagination links fixed semantically.

Do not reintroduce deleted dead modules without a concrete reason.

---

# 28. Current limitations

Intentionally not implemented yet:

- cross-source canonical deduplication;
- job lifecycle / stale job handling;
- seniority intelligence;
- salary normalization/intelligence;
- geography/eligibility intelligence;
- multilingual vacancy detection/extraction;
- user profiles;
- skill-gap analysis;
- personalized recommendations;
- AI advisor;
- portfolio recommendations;
- learning plans;
- scheduled background updates;
- PostgreSQL;
- production deployment;
- authentication;
- bots;
- local-market sources;
- production monitoring.

These are roadmap items, not bugs simply because they are absent.

---

# 29. Next data-quality capabilities

Before the product becomes strongly personalized, high-value structured job dimensions should be added.

Recommended priority:

1. job lifecycle / stale postings
2. seniority
3. geography / remote eligibility
4. salary normalization
5. cross-source canonical deduplication v1

Exact ordering may change based on real dataset observations.

Do not implement all of these simultaneously in one giant sprint.

---

# 30. Job lifecycle

Future work should distinguish:

- first seen;
- last seen;
- still active;
- stale;
- removed;
- expired where known.

Collectors are snapshots/observations, not eternal truth.

A dashboard must not treat every posting ever seen as currently open.

Lifecycle semantics should be source-aware but normalized.

---

# 31. Seniority

Future normalized seniority might include:

```text
intern
junior
mid
senior
lead
staff
principal
manager
director
executive
unknown
```

Do not infer seniority too aggressively.

Use explicit evidence where possible.

Keep deterministic and versioned analysis if practical.

---

# 32. Geography / work arrangement

The product is remote-first, not permanently remote-only.

Future normalized work arrangement:

```text
remote
hybrid
onsite
unknown
```

Also model separately:

- job location;
- eligible countries;
- eligible regions;
- worldwide remote;
- timezone constraints;
- relocation where relevant.

Do not conflate user location with job eligibility.

A user in Nigeria may search:

```text
Nigeria local
+
Worldwide remote
```

A user in Germany may search:

```text
Germany
+
EU remote
+
Worldwide remote
```

---

# 33. Salary intelligence

Future salary work should separate:

- raw salary text;
- parsed minimum;
- parsed maximum;
- currency;
- interval/unit;
- normalized annual equivalent when defensible;
- confidence;
- source evidence.

Do not convert salaries blindly when:

- period is unknown;
- currency is ambiguous;
- equity/bonus dominates;
- contractor rates cannot be safely annualized.

---

# 34. Cross-source canonical deduplication

This is a major future feature.

Current analytics count source postings.

A single real-world vacancy may appear in:

- Remote OK;
- Himalayas;
- WWR;
- a company ATS;
- other aggregators.

Future canonical linking should be conservative.

Likely signals:

- company identity;
- normalized title;
- location;
- application URL;
- ATS job ID;
- description fingerprints;
- posting time;
- salary/location overlap.

False merges are often worse than leaving duplicates separate.

Start conservative.

---

# 35. Global source expansion

The six existing sources are only the beginning.

The project should continue adding high-value sources after the core update pipeline is stable.

Preferred expansion path:

## Phase A: global aggregators / remote sources

Continue selectively where quality and access justify it.

## Phase B: ATS-backed company sources

Prioritize:

- Greenhouse
- Lever
- Ashby

Build curated company-board support rather than attempting uncontrolled scraping of the entire internet.

## Phase C: vertical sources

Potentially:

- Web3
- AI/ML
- software engineering
- startups
- design/product
- freelance/short contracts

## Phase D: local/regional sources

Only after the global core is strong.

Examples:

- Germany
- India
- Nigeria
- Ukraine
- Netherlands
- other markets

The source system must allow this growth without coupling source identity to UI language.

---

# 36. User Profile

A major product milestone is a structured user profile.

Potential fields:

- current role;
- years of experience;
- skills;
- skill proficiency;
- target role;
- target seniority;
- location;
- desired geography;
- desired work arrangement;
- desired salary;
- preferred job language;
- preferred response language;
- portfolio links;
- GitHub profile;
- learning constraints;
- time available;
- optional resume/CV.

User-profile data must remain logically separate from the global market dataset.

---

# 37. Skill Gap

The core personalized intelligence should compare:

```text
user profile
        +
target role
        +
current market evidence
        ↓
skill gap
```

Example:

```text
User has:
Python
SQL
Git

Target:
Backend

Market frequently asks for:
Python
PostgreSQL
Docker
AWS
CI/CD

Gap:
PostgreSQL
Docker
AWS
CI/CD
```

The system should rank gaps by market relevance, not simply list missing keywords.

---

# 38. Learning recommendations

The product should eventually recommend:

- what to learn;
- in what order;
- why it matters;
- how strongly the current market demands it;
- what prerequisite knowledge is useful;
- which practical project proves the skill.

Recommendations must be evidence-informed.

Do not claim guaranteed employment outcomes.

---

# 39. AI leverage recommendations

The product should not merely say “learn AI.”

It should help users understand where AI tools improve their work.

Examples:

- coding assistance;
- tests;
- documentation;
- research;
- debugging;
- data exploration;
- design ideation;
- customer support;
- marketing workflows;
- analysis;
- automation.

Future recommendations may map AI tools/use cases to:

- target role;
- skill gap;
- market expectations;
- user experience.

Avoid hype and vague advice.

---

# 40. Portfolio recommendations

A strong future differentiator is converting market gaps into buildable projects.

Example:

```text
Target role:
Backend

Gap:
Docker
PostgreSQL
CI/CD

Recommended portfolio project:
Production FastAPI service with PostgreSQL,
Docker, automated tests and CI/CD.
```

The project recommendation should explain:

- which missing skills it demonstrates;
- why employers value them;
- what minimum deliverable proves competence;
- optional advanced extensions.

---

# 41. AI architecture

AI should be provider-agnostic.

Do not couple the product to a single vendor.

Potential provider interface:

```text
AIProvider
├── OpenAI-compatible
├── Groq
├── OpenRouter
├── DeepSeek-compatible
├── local model
└── future providers
```

Use low-cost/free options where feasible.

The AI layer should consume structured evidence, not query raw vacancy data unnecessarily.

Preferred architecture:

```text
Database / analytics
        ↓
structured market evidence
        ↓
recommendation engine
        ↓
LLM explanation
```

This reduces:

- hallucination;
- token cost;
- latency;
- vendor dependency.

---

# 42. Multilingual AI output

The early multilingual feature should likely focus on:

- explanation;
- translation;
- conversational interaction;
- recommendations.

For example, a Ukrainian-speaking user may query the global English market but receive the explanation in Ukrainian.

The deterministic intelligence can remain English/language-neutral.

This is a high-leverage way to internationalize without duplicating the entire analysis engine per language.

---

# 43. Website roadmap

A public website should not wait until every advanced feature is finished.

Recommended deployment sequence:

```text
Current local MVP
        ↓
Data quality improvements
        ↓
Deployment foundation
        ↓
Hosted read-only alpha
        ↓
Accounts / personalization
        ↓
AI advisor
        ↓
Bots
        ↓
Public beta / v1
```

A first public alpha can simply expose:

- Overview
- Jobs
- Roles
- Skills
- Sources

No login is required for the first read-only alpha.

This allows:

- infrastructure validation;
- real user feedback;
- a public demo URL;
- stronger grant/hackathon applications.

---

# 44. Hosted infrastructure strategy

Likely early production architecture:

```text
Domain
  ↓
Cloudflare or DNS provider
  ↓
Reverse proxy
  ↓
Docker Compose on Linux VPS
  ├── frontend
  ├── API
  ├── worker
  └── PostgreSQL
```

Possible reverse proxies:

- Caddy
- nginx

Do not overengineer this before deployment.

---

# 45. SQLite and PostgreSQL strategy

SQLite remains valuable.

Target support:

## Local/self-hosted simple mode

```text
SQLite
```

## Hosted/multi-user mode

```text
PostgreSQL
```

Do not create separate business logic.

Preferred long-term design:

```text
repository interfaces
        ↓
SQLite implementation
PostgreSQL implementation
```

Migration to PostgreSQL should happen when the hosted multi-user architecture needs:

- concurrent writers;
- worker + API;
- user profiles;
- larger datasets;
- production operations;
- backups and restore;
- more robust indexing/querying.

Do not migrate solely for fashion.

---

# 46. Scheduler / worker

Current local update command is manual:

```text
job-market-analyzer update --database ...
```

Hosted deployment should eventually schedule collection.

Likely:

```text
scheduler
   ↓
update worker
   ↓
source collectors
   ↓
database
   ↓
analysis
```

Different sources may have different schedules.

Do not assume every source should refresh at the same interval.

Respect source rate limits and terms.

---

# 47. Cross-platform requirement

The final open-source product should support:

- Windows
- Linux
- macOS

The fact that development began on Windows does not prevent this.

Potential portability risks to audit:

- Windows-specific paths;
- PowerShell-only commands;
- CRLF/LF differences;
- filesystem behavior;
- SQLite URI handling;
- shell assumptions;
- process management;
- Node/Python install instructions.

Recommended universal distribution path:

```text
Docker Compose
```

Native development instructions should still exist for each supported OS where practical.

---

# 48. Bots

Bots are interfaces, not separate products.

Future model:

```text
Telegram bot
      ↓
API
      ↓
same core

WhatsApp bot
      ↓
API
      ↓
same core

Discord bot
      ↓
API
      ↓
same core
```

Do not implement independent scraping, analytics, or recommendation logic inside bots.

A bot should call stable API endpoints.

---

# 49. Authentication

Authentication is not yet implemented.

Do not add it before the hosted product needs user profiles.

Future options should be selected based on:

- simplicity;
- security;
- low cost;
- self-hosted compatibility.

Avoid locking the core product to a proprietary identity provider.

---

# 50. Privacy

Personal career data may include sensitive private information.

Future privacy principles:

- collect only what is needed;
- do not sell personal user data;
- separate market data from personal profiles;
- support self-hosted/local use;
- allow users to delete their profile;
- never expose API keys;
- encrypt secrets appropriately;
- minimize data sent to external AI providers.

Where possible, users should retain control of their own data.

---

# 51. Security

Before public hosting, perform a focused security sprint covering at minimum:

- secret management;
- production CORS;
- authentication;
- authorization;
- rate limiting;
- input validation;
- SQL injection safety;
- SSRF risk in future URL features;
- prompt injection boundaries for AI features;
- dependency scanning;
- production headers;
- admin/worker separation;
- backup strategy;
- logs without secrets.

The current local-loopback assumptions are not sufficient for public hosting.

---

# 52. Public API direction

A future public API is strategically useful.

Potential consumers:

- first-party website;
- Telegram bot;
- WhatsApp bot;
- Discord bot;
- external developers;
- open-source custom clients.

Do not expose internal database representations directly.

Maintain stable API contracts.

Version public APIs when breaking changes become likely.

---

# 53. Open-source usability

The repository should eventually offer:

- clear README;
- quick start;
- `.env.example`;
- Docker Compose;
- migrations;
- sample configuration;
- source credential documentation;
- troubleshooting;
- contribution guide;
- architecture docs;
- tests;
- supported platforms;
- security policy;
- license.

The ideal user experience should approach:

```text
clone
configure
start
use
```

not:

```text
spend hours manually wiring internal modules
```

---

# 54. CLI principles

Existing individual CLI commands must remain useful for debugging and source-specific operations.

Current commands include:

- collect-remote-ok
- collect-web3-career
- collect-himalayas
- collect-jobicy
- collect-remotive
- collect-we-work-remotely
- analyze-skills
- analyze-roles
- update
- serve

`update` is orchestration, not a replacement for lower-level commands.

Future commands may include:

- migrations;
- source status;
- admin diagnostics;
- profile import/export;
- evaluation.

Avoid turning the CLI into an unmaintainable command tree.

---

# 55. Product honesty

Never overclaim dataset quality.

Until canonical deduplication exists, say:

```text
source postings
```

not:

```text
unique jobs
```

Until job lifecycle exists, do not imply every historical posting is still open.

Until salary confidence is strong, do not imply perfect compensation coverage.

Until language-specific analysis exists, do not pretend it does.

Until a recommendation has enough market evidence, communicate uncertainty.

---

# 56. Real-data validation

Do not rely exclusively on unit tests.

After major data/intelligence changes:

1. run against a real personal dataset;
2. inspect samples;
3. inspect coverage;
4. inspect false positives;
5. inspect false negatives;
6. compare dashboard output;
7. document problems.

The user’s own dataset is an important product-development feedback loop.

---

# 57. Current real source validation history

Prior live smoke observations included approximately:

- Himalayas: 60 fetched / 52 persisted on first run;
- Jobicy: 50 / 50;
- Remotive: 18 / 18;
- We Work Remotely: 99 fetched / 98 persisted.

Combined validation corpus previously reached hundreds of source postings.

These figures are historical smoke-test observations, not stable product metrics.

Do not hardcode or market them.

---

# 58. Current skill/role validation history

Historical smoke validation:

Skill extraction on one combined sample:

- Remote OK: 16/100
- Web3.career: 67/100
- combined: 83/200

Role extraction:

- Remote OK: 11/100
- Web3.career: 82/100
- combined: 93/200
- 5 multilabel cases
- no pure-vs-persisted mismatches in that validation

These numbers demonstrate functionality, not final quality.

Future evaluation should be more systematic.

---

# 59. Evaluation roadmap

As the intelligence grows, introduce explicit evaluation datasets.

Useful future evals:

- role classification precision/recall;
- skill extraction precision/recall;
- salary parsing;
- seniority parsing;
- geography normalization;
- canonical deduplication;
- recommendation relevance;
- multilingual output quality.

Prefer small reviewed gold datasets over vague “looks good” checks.

---

# 60. Recommended next development phases

## Phase 1 — Stabilize personal/global dataset

- run guided six-source update;
- inspect real dashboard;
- identify practical quality issues;
- improve job lifecycle;
- improve high-value parsing;
- preserve all existing invariants.

## Phase 2 — Data Quality v1

- seniority;
- geography;
- salary;
- lifecycle;
- conservative canonical deduplication.

## Phase 3 — Global Source Expansion v2

Prioritize:

- Greenhouse
- Lever
- Ashby

Continue other global sources selectively.

Do not stop at six sources.

## Phase 4 — Deployment Foundation

- cross-platform audit;
- Docker;
- production configuration;
- PostgreSQL adapter/migration;
- worker/scheduler;
- backups;
- health/readiness;
- production reverse proxy.

## Phase 5 — Hosted Read-Only Alpha

Deploy:

- Overview
- Jobs
- Roles
- Skills
- Sources

No login initially required.

## Phase 6 — User Intelligence

- user profile;
- target role;
- skill gap;
- market-backed recommendations.

## Phase 7 — AI Advisor

- provider abstraction;
- low-cost model support;
- structured evidence input;
- natural-language explanation.

## Phase 8 — Multilingual Experience

- multilingual user output;
- localized UI;
- conversational language preferences;
- later multilingual vacancy analysis where needed.

## Phase 9 — Learning + Portfolio

- learning sequence;
- project recommendations;
- AI-tool recommendations;
- evidence-based explanations.

## Phase 10 — Bots

- Telegram;
- WhatsApp;
- optionally Discord.

All use the same API.

## Phase 11 — Local Market Expansion

Country/region-specific sources and language-aware ingestion after the global core is mature.

---

# 61. Grants / hackathons / distribution

Grants and hackathons are opportunities, not the product mission.

The product should not be distorted to fit one grant.

However, grants can provide:

- funding;
- visibility;
- community;
- credibility;
- distribution;
- feedback.

One relevant organization already identified:

```text
Sentient Foundation
```

Relevant public pages previously reviewed:

```text
https://sentient.foundation/product-requests
https://sentient.foundation/grants
```

The project appears conceptually aligned with open AI, accessibility, global users, multilingual reach, and public-good tooling.

A future agent should independently verify current:

- eligibility;
- grant requirements;
- product requests;
- deadlines/rolling status;
- required AI/open-source components;
- submission format;
- evaluation criteria.

Do not rely solely on this document because grant terms can change.

---

# 62. Grant positioning

Do not pitch the project as:

> a job scraper.

A stronger positioning:

> An open-source AI career-intelligence platform that helps anyone understand the global job market, identify missing skills, decide what to learn and build next, and target realistic jobs — with evidence from real market data and explanations in the user’s language.

Possible product positioning:

```text
SkillSignal — Open Career Intelligence for Everyone
```

or:

```text
SkillSignal — An Open AI Career Navigator for the Global Workforce
```

Branding is not finalized.

---

# 63. AI / grant demo milestone

A strong grant/hackathon demo could show:

```text
global market data
+
user target role
+
known skills
+
skill-gap calculation
+
evidence-backed recommendations
+
AI explanation
+
multilingual output
+
portfolio recommendation
```

Example:

```text
User:
Backend developer
Location: India
Skills: Python, SQL, Git
Target: Remote worldwide

System:
Strong match: Backend
High-value gaps: Docker, PostgreSQL, AWS, CI/CD
Recommended next project: FastAPI + PostgreSQL + Docker + CI/CD
Explanation: generated from current market evidence
```

This should be a real product capability, not a hackathon-only mockup.

---

# 64. Product interfaces

Long-term architecture:

```text
                         ┌── Web Dashboard
                         │
                         ├── Telegram Bot
                         │
Core / API ──────────────┼── WhatsApp Bot
                         │
                         ├── Discord Bot
                         │
                         ├── CLI
                         │
                         └── Third-party API
```

No interface owns market logic.

---

# 65. Deployment stages

## Local Development

Current:

```text
Windows + Python virtualenv + Node
```

This remains valid.

## Cross-platform Development

Add:

- Linux verification;
- macOS verification;
- OS-neutral paths;
- Docker.

## Hosted Alpha

Use a low-cost Linux VPS.

## Production Growth

Only after real usage justifies it consider:

- separate DB host;
- managed PostgreSQL;
- object storage;
- queues;
- multiple workers;
- CDN;
- autoscaling.

Do not pre-build these.

---

# 66. Local startup commands

Backend:

```powershell
cd D:\Documents\Crypto\SOFT_CRYPTO\job-market-analyzer
.\.venv\Scripts\Activate.ps1
job-market-analyzer serve --database .\job-market.sqlite3
```

Frontend in a second terminal:

```powershell
cd D:\Documents\Crypto\SOFT_CRYPTO\job-market-analyzer\web
npm run dev
```

Open:

```text
http://localhost:3000
```

Guided dataset update:

```powershell
job-market-analyzer update --database .\job-market.sqlite3
```

---

# 67. Python test command

Use:

```powershell
python -m pytest
```

Do not rely on bare:

```text
pytest
```

because a prior environment had a stale Python 3.10 `pytest` on PATH while the project virtual environment used Python 3.13.

Current project Python used in latest tests:

```text
Python 3.13.7
```

---

# 68. Credential handling

Before any workflow that requires a new:

- API key;
- token;
- OAuth authorization;
- billing account;
- external account;

the user should be told explicitly.

Never ask users to paste secrets into chat.

Existing known credential:

```text
WEB3_CAREER_API_TOKEN
```

For a PowerShell session:

```powershell
$env:WEB3_CAREER_API_TOKEN="..."
```

Persistent Windows user environment variable can be set separately if desired.

The guided update command already skips Web3.career when this token is unavailable.

---

# 69. Documentation files to inspect

A new agent should inspect at minimum:

```text
README.md
PROJECT_HANDOFF.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/ROADMAP.md
docs/SOURCES.md
docs/UPDATE_FLOW.md
```

Also inspect:

- migrations;
- repository interfaces;
- SQLite implementation;
- collectors;
- normalizers;
- services;
- CLI;
- API;
- tests;
- frontend API client.

---

# 70. Git discipline

The project is currently developed on `main`.

Before large changes:

```text
git status
```

After implementation:

```text
ruff check .
python -m pytest -v
git diff --check
```

If frontend changes:

```text
npm test
npm run lint
npm run typecheck
npm run build
```

Use one coherent commit per meaningful sprint.

Do not commit generated build artifacts, secrets, databases, or virtual environments.

---

# 71. Review discipline

Avoid endless cycles of:

```text
implement
review
hardening
review
hardening
review
```

The project previously burned excessive coding-agent limits this way.

Preferred working model:

1. define a meaningful vertical sprint;
2. implement it;
3. run one quality gate;
4. perform one self-review;
5. fix actual blockers/high-risk issues;
6. commit;
7. move to the next product milestone.

Additional reviews should be triggered by real risk, not by habit.

---

# 72. Engineering style

Prefer:

- explicit contracts;
- deterministic behavior;
- typed registries;
- small services;
- testable functions;
- repository abstractions;
- idempotency;
- versioned analysis;
- honest semantics;
- minimal framework complexity.

Avoid:

- giant abstractions before needed;
- duplicated source logic;
- source-specific behavior spread throughout the code;
- UI-specific business logic;
- LLM-first architecture;
- silent failure;
- hidden credential assumptions.

---

# 73. Things that must not be accidentally broken

Before modifying foundations, preserve or explicitly migrate:

1. source posting identity;
2. raw observation sequencing;
3. event-time freshness;
4. stale observation persistence;
5. idempotency;
6. versioned role/skill runs;
7. exact-current analyzer resolution;
8. analyzer-kind isolation;
9. posting-level analytics semantics;
10. read-only API connections;
11. secret redaction;
12. current CLI compatibility;
13. guided update partial-failure policy;
14. historical analysis retention;
15. source registry-driven orchestration.

---

# 74. Source-specific behavior should stay isolated

Collectors and normalizers exist because remote sources differ.

Do not make generic persistence aware of arbitrary source-specific HTML/JSON quirks.

Preferred boundary:

```text
source weirdness
→ collector / normalizer
→ stable normalized model
→ generic persistence
```

---

# 75. Future source onboarding checklist

When adding a source:

1. Verify legal/technical access pattern.
2. Determine authentication requirement.
3. Identify stable external ID.
4. Define source scope.
5. Implement collector.
6. Implement normalizer.
7. Reuse common models.
8. Register SourceAdapter.
9. Add deterministic tests.
10. Add no-network test coverage.
11. Run a controlled live smoke.
12. Check idempotency.
13. Check malformed response behavior.
14. Check stale/out-of-order behavior if timestamps exist.
15. Document credential requirements.
16. Update source docs.

---

# 76. Future analyzer onboarding checklist

When adding an analyzer:

1. Define analyzer kind.
2. Define language capability.
3. Define version.
4. Define input identity/hash.
5. Define deterministic behavior or AI contract.
6. Persist versioned runs.
7. Preserve historical results.
8. Register AnalyzerAdapter.
9. Add exact-current tests.
10. Add zero-result semantics.
11. Add real-data evaluation.
12. Expose in analytics only when trustworthy.

---

# 77. Future AI analyzer caution

If AI is later used for extraction:

- store provider/model/version metadata;
- preserve prompt/version identity;
- avoid non-repeatable silent changes;
- cache results;
- separate AI extraction from AI explanation;
- measure quality against deterministic/evaluation baselines;
- never send secrets or unnecessary personal data;
- provide fallback behavior.

Do not casually replace deterministic skills/roles with an LLM.

---

# 78. Public website initial scope

A useful public alpha can be modest.

Initial pages:

- market overview;
- jobs;
- roles;
- skills;
- sources;
- methodology/about.

Potential additions:

- “last updated” timestamp;
- source health;
- market coverage disclaimer.

Do not wait for accounts or AI to deploy the read-only intelligence.

---

# 79. User-facing trust

Future public product should explain:

- where data comes from;
- how often it updates;
- that source postings may overlap;
- that recommendations are guidance, not guarantees;
- that salaries can be incomplete;
- that AI-generated explanations are grounded in structured evidence;
- that users control their profile data.

Trust will matter as much as feature count.

---

# 80. Observability

Before public hosting add at least:

- structured application logs;
- source update status;
- source failure counts;
- last successful update time;
- health endpoint;
- readiness checks;
- database backup verification.

Avoid logging:

- API keys;
- tokens;
- full sensitive profiles.

---

# 81. Backups

Hosted PostgreSQL must have a real backup strategy before relying on it.

At minimum:

- automated database backup;
- retention policy;
- restore test;
- secrets stored separately;
- backup monitoring.

A backup that has never been restored is not proven.

---

# 82. Production configuration

Future production config should be environment-based.

Likely categories:

- database URL;
- application environment;
- public API URL;
- frontend URL;
- CORS origins;
- source credentials;
- AI provider credentials;
- bot credentials;
- logging;
- scheduler configuration.

Provide `.env.example`.

Never commit real `.env`.

---

# 83. Containerization

Docker should be introduced as a deployment/cross-platform tool, not as a rewrite of the product.

Likely services:

```text
web
api
worker
postgres
```

For local self-hosting, support a simple profile where possible.

Do not force advanced contributors to use Docker if native development remains useful.

---

# 84. PostgreSQL migration principles

When PostgreSQL work begins:

- preserve repository interfaces;
- preserve domain semantics;
- preserve idempotency;
- preserve exact-current analysis;
- preserve transaction guarantees;
- create migration tooling;
- add integration tests;
- test real concurrency;
- compare analytics results between SQLite/PostgreSQL;
- do not abandon SQLite immediately.

---

# 85. Performance

Current SQLite analytics may use Python SHA UDF/full scans in places.

The independent audit judged this acceptable at current scale.

Do not prematurely optimize.

When real data grows:

1. measure;
2. identify slow queries;
3. inspect query plans;
4. add indexes/materialization where justified;
5. move expensive aggregates to PostgreSQL/materialized summaries only when needed.

---

# 86. Hosted alpha trigger

A reasonable trigger for hosted alpha is:

- dashboard stable;
- guided update stable;
- lifecycle semantics at least minimally usable;
- data-quality caveats understood;
- deployment foundation complete;
- production-safe API configuration;
- PostgreSQL ready or a deliberate temporary SQLite alpha design.

The website does not need the entire long-term roadmap completed.

---

# 87. Product success

The project is successful if users can make better career decisions from real market evidence.

Not merely if:

- many sources are scraped;
- many rows exist;
- AI can chat.

The important outcome is whether a user can answer:

```text
What can I realistically target?
What am I missing?
What should I learn next?
What should I build?
Why?
```

with evidence from the current market.

---

# 88. Near-term agent instruction

A new coding agent should NOT immediately start rewriting foundations.

First:

1. inspect repository;
2. run tests;
3. verify guided update commit is present;
4. run a real six-source update if credentials/network allow;
5. inspect dashboard;
6. document concrete data-quality problems;
7. select the highest-value next vertical sprint.

Likely next candidates:

- lifecycle;
- seniority;
- geography;
- salary;
- ATS source expansion;
- deployment preparation.

Choose based on observed product value, not novelty.

---

# 89. Recommended first cross-platform task

Before public self-hosted release:

- run Windows test suite;
- run Linux CI;
- add macOS CI if practical;
- remove platform-specific paths;
- add Docker build;
- document native Windows/Linux/macOS setup;
- ensure SQLite and frontend work in containers;
- ensure no shell-specific runtime assumptions.

GitHub Actions is a natural place for OS matrix validation.

---

# 90. GitHub/open-source direction

The repository is intended to become public.

Before public launch:

- choose license;
- remove secrets/history issues;
- ensure no personal database committed;
- add CONTRIBUTING;
- add SECURITY;
- add CODE_OF_CONDUCT if desired;
- clean README;
- add screenshots/demo;
- document roadmap;
- document supported sources;
- document API keys.

A public repo should be understandable without private chat context.

This handoff file helps with that transition.

---

# 91. Branding / product copy

Do not over-focus on the technical name.

The product proposition should be obvious in one sentence.

Possible wording:

> Open, evidence-backed career intelligence for the global workforce.

Longer:

> A global open-source career-intelligence platform that analyzes real job-market demand and helps people understand what roles to target, what skills they are missing, what to learn next, what to build for a portfolio, and how AI can improve their work.

---

# 92. Scope boundaries

Do not let the product become:

- a generic LinkedIn clone;
- a generic ATS;
- a generic course marketplace;
- an ungrounded AI career chatbot;
- a full recruitment CRM;
- a resume spam tool.

The strongest identity is:

```text
market intelligence
+
personal skill gap
+
actionable career development
```

---

# 93. Data ethics

When adding sources:

- respect access constraints;
- prefer official APIs/RSS/public endpoints;
- rate-limit responsibly;
- avoid circumventing security controls;
- document source terms and risks;
- do not collect unnecessary personal data.

The project should be technically robust and ethically defensible.

---

# 94. Local-market expansion

Local sources are a later phase.

When implemented, keep the same core model.

Example:

```text
Global English sources
        +
German local sources
        +
Indian local sources
        +
Nigerian/African sources
        +
Ukrainian sources
```

But do not fork the product by country.

Normalize into the same global schema.

---

# 95. Search experience

Future search should support more than keyword matching.

Long-term filters may include:

- role;
- skill;
- seniority;
- salary;
- company;
- source;
- work arrangement;
- region/country;
- timezone;
- language;
- date freshness.

Semantic/NL search can be layered later.

Do not remove deterministic filters just because natural-language search is added.

---

# 96. Recommendation explainability

Every important recommendation should ideally answer:

```text
Why are you telling me this?
```

Examples:

- “Docker appears in X% of matching backend postings.”
- “AWS is frequently paired with Python in your target role.”
- “Your current profile already matches A/B/C requirements.”
- “This portfolio project demonstrates three of your highest-value gaps.”

The explanation should come from evidence, not persuasion.

---

# 97. Potential future user workflow

Example end-to-end product experience:

```text
1. User selects location and preferred language.
2. User chooses target role.
3. User enters current skills or imports profile.
4. Product loads current relevant market data.
5. Product calculates skill match/gap.
6. Product shows realistic job opportunities.
7. Product recommends learning priorities.
8. Product recommends AI tools/workflows.
9. Product proposes portfolio projects.
10. Product generates a personalized plan.
11. User can receive updates through web/bot.
```

This is a product destination, not all current functionality.

---

# 98. Notifications

Future notifications may include:

- new high-fit jobs;
- meaningful market changes;
- rising skill demand;
- expiring/stale tracked opportunities;
- learning-plan reminders if user opts in.

Notifications should be useful and non-spammy.

Bots are natural delivery channels.

---

# 99. What not to do next

Do not:

- add 20 random sources before measuring quality;
- build a huge LLM agent framework;
- migrate to microservices;
- add Kubernetes;
- rewrite working persistence;
- localize every internal identifier;
- build separate bot logic;
- optimize only for Sentient;
- overclaim production readiness;
- add local country sources before global model quality is understood.

---

# 100. Immediate handoff conclusion

The project has moved beyond an experiment.

It currently has:

- a real multi-source ingestion pipeline;
- durable persistence;
- versioned skills/roles intelligence;
- analytics;
- API;
- frontend dashboard;
- guided end-to-end update command;
- strong regression test coverage;
- documented architectural invariants.

The next development stage should turn this healthy local MVP into a stronger global product.

The six current sources are the starting set, not the destination.

The strategic direction is:

```text
MORE HIGH-QUALITY GLOBAL SOURCES
        ↓
BETTER STRUCTURED JOB INTELLIGENCE
        ↓
HOSTED GLOBAL WEBSITE
        ↓
USER PROFILE + SKILL GAP
        ↓
AI + MULTILINGUAL EXPLANATION
        ↓
LEARNING + PORTFOLIO GUIDANCE
        ↓
TELEGRAM / WHATSAPP / DISCORD
        ↓
LOCAL MARKET EXPANSION
```

The project should remain:

- open source;
- self-hostable;
- cross-platform;
- evidence-driven;
- low-cost where possible;
- globally useful;
- honest about uncertainty;
- extensible without unnecessary complexity.

---

# 101. First message for a new coding agent

A new agent should be given this instruction:

```text
Open this repository and treat it as an existing product, not a greenfield rewrite.

Before changing anything, read:

PROJECT_HANDOFF.md
README.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/ROADMAP.md
docs/SOURCES.md
docs/UPDATE_FLOW.md

Then inspect the actual implementation, migrations, tests, CLI, API and frontend.

Run the existing quality gates and verify the repository state before proposing changes.

The product mission is to build a global, open-source career-intelligence platform:
real job-market data → structured intelligence → skill gap → learning/portfolio/AI recommendations → multilingual user experience.

The current six job sources are only the first source set. Continue expanding high-quality global sources over time, especially ATS-backed sources such as Greenhouse, Lever and Ashby, without rewriting the orchestration architecture.

Do not optimize the project around a single grant or hackathon. Grants are optional distribution/funding opportunities.

Preserve the documented persistence, hashing, idempotency, analyzer-versioning and exact-current semantics unless a migration explicitly changes them.

Prefer meaningful vertical product sprints and one quality gate over endless review/hardening cycles.

For the next sprint, inspect the real dataset/dashboard first and recommend the highest-value next step based on observed product quality and the roadmap.
```

---

# 102. Final rule

Always optimize for the real product:

> Help a person understand the market, understand themselves, close the right gaps, and move toward better work.

Everything else — sources, AI, website, bots, grants, infrastructure — exists to support that goal.
