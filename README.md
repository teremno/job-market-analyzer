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

Repeated observations from the same source update one JobPosting. Cross-source duplicates remain separate JobPostings linked to one CanonicalJob, so provenance is preserved while analytics can count the vacancy once.

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

Install the package locally, then run one real Remote OK collection with an explicit SQLite path:

```bash
python -m pip install -e .
```

```bash
job-market-analyzer collect-remote-ok --database ./job-market.sqlite3
```

This command makes a real network request to Remote OK, initializes or reuses the selected SQLite database, prints a concise result and a sample of up to five vacancies, then exits. It does not start a scheduler or background process. Repeated runs against the same database reuse and upsert existing source postings; the command never deletes or recreates the database.
