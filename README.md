# Job Market Analyzer

Job Market Analyzer is a research-oriented system for collecting and analyzing remote job opportunities.

The main goal is not simply to find job listings.

The project should help answer:

- Which remote professions are currently in demand?
- Which technologies and skills are requested most often?
- Which skills are required vs. optional?
- Which professions have the lowest barrier to entry?
- Which jobs can be accelerated or partially automated with AI tools?
- Which technologies provide the biggest increase in available job opportunities?
- What salaries are offered for different roles?
- Which roles are realistic for junior or entry-level candidates?
- Which remote jobs are available to candidates in Europe or worldwide?

## Main pipeline

External source
→ RawJob
→ NormalizedJobPosting
→ Repository persistence
→ JobPosting
→ CanonicalJob
→ Later structured extraction and analytics

`RawJob` preserves the original source observation. `JobPosting` is the durable posting on one source, while `CanonicalJob` groups postings that represent the same real-world vacancy.

Repeated observations from the same source update one `JobPosting`. Cross-source duplicates remain separate postings; once a future high-confidence linker associates them with one `CanonicalJob`, provenance remains available while canonical analytics can count the vacancy once. Automatic cross-source linking is not implemented yet.

Persistence is deterministic: timestamps use a fixed UTC format, JSON keys are sorted, Decimal values never pass through binary floats, and persistence owns both raw `observation_hash` and normalized `content_hash` values.

## Initial research focus

Collection is not filtered by profession or role: each collector stores every vacancy
its connected source exposes. The product is remote-first through source selection,
not through a fixed vacancy whitelist.

The roles below are only the initial research interests used when validating the first
sources and analyzers. They are not a product boundary. The role taxonomy (currently
19 stable codes plus an explicit Unknown state) keeps expanding together with the
source set, and users search whatever the collected dataset contains.

- AI Automation
- Python Automation
- API / Integration Development
- Junior Backend Development
- QA / Software Testing
- Data Analysis
- Technical Support
- OSINT / Investigative Research
- Due Diligence / KYC
- Cyber Threat Intelligence
- AI Operations
- Web / CMS / WordPress
- Web3 / Blockchain
- Crypto Investigations

## Project status

Early development / research phase.

See [Product Vision](docs/PRODUCT_VISION.md) for long-term principles and [Product Roadmap](docs/ROADMAP.md) for current progress and future phases.

## Guided dataset update

Run every enabled source, persist current observations, and then run the active
English analyzers (skills, roles, seniority, geography, salary) with one command:

```powershell
job-market-analyzer update --database .\job-market.sqlite3
```

The database path is required and may be new or existing. Sources run once in the
explicit registry order: Remote OK, Web3.career, Himalayas, Jobicy, Remotive, We
Work Remotely, Greenhouse, Lever, and Ashby. The three ATS sources collect curated
company boards through one credential-free request per board; their approved board
lists live in `docs/SOURCES.md` and grow by one-token registry additions rather
than new CLI commands. If `WEB3_CAREER_API_TOKEN` is absent, Web3.career alone is
reported as skipped; credential-free sources still run. Never commit the token or
pass it as a CLI argument. A failed remote source is reported and later independent
sources continue, while a database, schema, or persistence failure aborts the
update. All registered analyzers run after collection over current durable
postings.

Repeated unchanged updates reuse source postings, observations, and versioned
analysis runs. Use repeatable `--source PROVIDER` to select registry entries and
`--limit-analysis N` only when an explicit bounded analysis pass is wanted. The
default analyzes all current postings. For example:

```powershell
job-market-analyzer update --database .\job-market.sqlite3 --source remote_ok --source jobicy
```

`--language` means analyzer input language, not CLI display language. The CLI remains
English. Current registrations are `skills/en`, `roles/en`, `seniority/en`,
`geography/en`, and `salary/en`, so
`--language uk` fails before collection with a clear not-implemented message; it does
not run English rules over Ukrainian text. The summary reports source-posting counts,
not globally deduplicated vacancies, and ends with the matching `serve` command. See
[Guided Update Flow](docs/UPDATE_FLOW.md) for the exact policy and extension seams.

## Manual one-shot collection

Install the package locally:

```bash
python -m pip install -e .
```

### Remote OK

Run one real Remote OK collection with an explicit SQLite path:

```bash
job-market-analyzer collect-remote-ok --database ./job-market.sqlite3
```

This command makes a real network request to Remote OK, initializes or reuses the selected SQLite database, prints a concise result and a sample of up to five vacancies, then exits. It does not start a scheduler or background process. Repeated runs against the same database reuse and upsert existing source postings; the command never deletes or recreates the database.

### Web3.career

Set the required `WEB3_CAREER_API_TOKEN` environment variable, then run one collection with an explicit SQLite path. For PowerShell:

```powershell
$env:WEB3_CAREER_API_TOKEN = "<YOUR_TOKEN>"
job-market-analyzer collect-web3-career --database ./web3-career-smoke.sqlite3
```

Never commit the token or store it in tracked files. The command reads it only from `WEB3_CAREER_API_TOKEN`, performs one authenticated API collection run, initializes or reuses the selected database, prints a token-safe summary and at most five vacancies, then exits. Repeated runs reuse the same database and its existing deduplication/upsert behavior.

### Public credential-free sources

The MVP also supports four structured, remote-focused public feeds that require no
account or API secret:

| Source | Access | Command |
|---|---|---|
| Himalayas | Public JSON API | `collect-himalayas` |
| Jobicy | Public JSON API | `collect-jobicy` |
| Remotive | Public JSON API | `collect-remotive` |
| We Work Remotely | Official RSS | `collect-we-work-remotely` |

Run any source once with an explicit SQLite database:

```bash
job-market-analyzer collect-himalayas --database ./himalayas-smoke.sqlite3
job-market-analyzer collect-jobicy --database ./jobicy-smoke.sqlite3
job-market-analyzer collect-remotive --database ./remotive-smoke.sqlite3
job-market-analyzer collect-we-work-remotely --database ./we-work-remotely-smoke.sqlite3
```

Each command performs a bounded collection and exits. Reusing the same database
preserves the existing same-source identity, observation provenance, and idempotent
upsert behavior. These integrations do not scrape job pages. Provider-specific
attribution and known feed limitations are documented in
[External Sources and Attribution](docs/SOURCES.md).

## Manual one-shot skill analysis

Analyze a bounded set of current durable postings already stored in SQLite:

```bash
job-market-analyzer analyze-skills --database ./job-market.sqlite3 --limit 100
```

`--database` is required, must identify an existing SQLite file, and `--limit` defaults to `100`. A missing path fails without creating an empty database. The command reads current `JobPosting` rows in deterministic source-identity order, runs the active deterministic Skill Taxonomy v2 extractor once for each selected posting, persists versioned analysis runs and evidence, prints posting-level coverage and bounded samples, then exits. It makes no network requests and does not start a scheduler or background process.

Repeated runs reuse identical analysis runs and create no duplicate evidence. If a posting's skill-analysis input changes, the command creates a new versioned run while preserving previous derived evidence for reproducibility.

The current summary is posting-level smoke coverage, not final deduplicated market analytics. Cross-source canonical linking remains incomplete, so these counts must not be interpreted as unique real-world vacancy demand.

Taxonomy v1 evidence remains preserved in historical analysis runs. See [Skill Taxonomy Validation Report](docs/SKILL_TAXONOMY_REPORT.md) for the local Remote OK/Web3.career validation, v2 rationale, measured coverage, and limitations.

## Manual one-shot role analysis

Analyze a bounded set of current durable postings already stored in SQLite:

```bash
job-market-analyzer analyze-roles --database ./job-market.sqlite3 --limit 100
```

`--database` is required, must identify an existing SQLite file, and `--limit` defaults to `100`. The command reads current `JobPosting` rows in deterministic `(source_provider, source_scope, external_id, id)` order, runs Role Taxonomy v2, persists versioned role runs and evidence, prints posting-level coverage plus bounded evidence, Unknown, and multi-label samples, then exits. It performs no collection or network request.

Unknown is a successful exact-version analysis with zero `RoleEvidence`, not a failure. Repeating the command with unchanged title, description, and analyzer version reuses every exact run without duplicating evidence. A changed role input creates a historical run; company, salary, location, tags, and other non-role changes do not.

The output is a manual development validation over source postings. It is not fully canonical-deduplicated market analytics because complete cross-source canonical linking is not implemented. See [Role Persistence Validation Report](docs/ROLE_PERSISTENCE_VALIDATION_REPORT.md) for the bounded local persisted-data results and limitations.

## Local Dashboard

Dashboard v0 is a local browser product for posting-level analytics. It provides
Overview, Jobs, Roles, Skills, and Sources pages without exposing descriptions, raw
payloads, database paths, or write operations.

### A. Populate one database

From the repository root in Windows PowerShell, run every collector against the same
path. These commands make real source requests:

```powershell
job-market-analyzer collect-remote-ok --database .\job-market.sqlite3
job-market-analyzer collect-web3-career --database .\job-market.sqlite3
job-market-analyzer collect-himalayas --database .\job-market.sqlite3
job-market-analyzer collect-jobicy --database .\job-market.sqlite3
job-market-analyzer collect-remotive --database .\job-market.sqlite3
job-market-analyzer collect-we-work-remotely --database .\job-market.sqlite3
```

Web3.career reads `WEB3_CAREER_API_TOKEN` only from the environment. Never commit,
paste into frontend configuration, or print that value.

### B. Analyze the persisted postings

```powershell
job-market-analyzer analyze-skills --database .\job-market.sqlite3 --limit 10000
job-market-analyzer analyze-roles --database .\job-market.sqlite3 --limit 10000
```

### C. Start the backend

Run the read-only local API against an existing current-schema SQLite database:

```powershell
job-market-analyzer serve --database .\job-market.sqlite3
```

The database path is required and must already exist. The server binds
`127.0.0.1:8000` by default, rejects non-loopback bind hosts, and never creates,
migrates, or writes the selected
database. Open `http://127.0.0.1:8000/docs` for local OpenAPI documentation. The API
base path is `/api`, with these Dashboard v0 endpoints:

- `GET /api/health`
- `GET /api/overview`
- `GET /api/jobs`
- `GET /api/roles/{role_code}`
- `GET /api/skills/{skill_code}`
- `GET /api/sources`

### D. Start the frontend

Open a second PowerShell window:

```powershell
cd web
npm install
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000`. Copy `web/.env.example` to a local
`.env.local` only when a different loopback API URL is needed.

### E. Open the product

Open `http://localhost:3000`. Current counts remain **source postings**, not globally
unique jobs, because complete cross-source canonical linking is not implemented.
See [Dashboard v0](docs/DASHBOARD_V0.md) for product scope and troubleshooting and
[Local API Contract](docs/API_CONTRACT.md) for exact HTTP semantics.
