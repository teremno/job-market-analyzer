# Architecture

## Goal

Build a modular system capable of collecting remote job listings from multiple sources and transforming them into structured data suitable for market analysis.

## High-Level Pipeline

Sources
↓
Collectors
↓
Raw Jobs
↓
Normalizer
↓
Deduplication
↓
Database
↓
AI / Structured Extraction
↓
Analytics
↓
Reports

## Planned Components

### 1. Collectors

Each source should have an independent collector.

Possible source types:

- REST API
- GraphQL API
- RSS / Atom
- Public JSON
- ATS APIs
- HTML scraping only when necessary

### 2. Normalizer

All collected jobs must be converted into a common internal schema.

Example fields:

- source
- external_id
- title
- company
- description
- url
- published_at
- remote
- remote_region
- salary_min
- salary_max
- salary_currency
- employment_type

### 3. Skill Extraction

Job descriptions will be analyzed to identify:

- required skills
- preferred skills
- programming languages
- frameworks
- databases
- cloud technologies
- AI tools
- automation tools
- required experience
- education requirements
- seniority

### 4. Analytics

The analytics layer should answer questions such as:

- Most demanded technologies
- Skills by profession
- Junior-accessible professions
- Remote availability
- Salary distributions
- Technology combinations
- Skills that unlock the largest number of additional jobs

## Engineering Principles

- Prefer public APIs, RSS, and structured feeds over scraping.
- Keep each collector independent.
- Store original raw data where practical.
- Normalize data before analysis.
- Do not bypass authentication, CAPTCHAs, Cloudflare, or access restrictions.
- Make data provenance traceable.
- Keep external-source attribution documented.