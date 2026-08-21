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

## Initial target roles

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

`--database` is required, must identify an existing SQLite file, and `--limit` defaults to `100`. The command reads current `JobPosting` rows in deterministic `(source_provider, source_scope, external_id, id)` order, runs Role Taxonomy v1, persists versioned role runs and evidence, prints posting-level coverage plus bounded evidence, Unknown, and multi-label samples, then exits. It performs no collection or network request.

Unknown is a successful exact-version analysis with zero `RoleEvidence`, not a failure. Repeating the command with unchanged title, description, and analyzer version reuses every exact run without duplicating evidence. A changed role input creates a historical run; company, salary, location, tags, and other non-role changes do not.

The output is a manual development validation over source postings. It is not fully canonical-deduplicated market analytics because complete cross-source canonical linking is not implemented. See [Role Persistence Validation Report](docs/ROLE_PERSISTENCE_VALIDATION_REPORT.md) for the bounded local persisted-data results and limitations.
