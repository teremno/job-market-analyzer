# AGENTS.md

## Project

Job Market Analyzer

## Objective

Build a maintainable system for collecting and analyzing remote job listings in order to understand:

- market demand
- technology requirements
- junior accessibility
- remote availability
- salary ranges
- AI-assisted work potential

## Rules for AI Coding Agents

### 1. Do not over-engineer

Prefer simple, understandable implementations.

Do not introduce:

- microservices
- Kubernetes
- complex distributed systems
- unnecessary abstractions

unless explicitly requested.

### 2. Work incrementally

Implement one clearly defined task at a time.

Do not redesign unrelated parts of the project.

### 3. Explain architecture changes

Before making significant architectural changes, explain:

- what should change
- why
- alternatives
- trade-offs

### 4. External repositories

Do not silently copy code from external repositories.

If external code, architecture, schemas, or substantial ideas are used:

- identify the source repository
- check the license
- document usage in docs/SOURCES.md

### 5. Data collection

Prefer data sources in this order:

1. Official REST APIs
2. Official GraphQL APIs
3. RSS / Atom
4. Public structured JSON
5. Public ATS endpoints
6. HTML scraping

Do not attempt to bypass:

- authentication
- CAPTCHAs
- Cloudflare challenges
- rate limits
- access restrictions

### 6. Python

Primary backend language: Python.

Code should:

- use type hints
- have clear names
- keep functions reasonably small
- separate collectors from analysis logic
- avoid global state where possible

### 7. Secrets

Never commit:

- API keys
- access tokens
- passwords
- cookies
- private credentials

Use environment variables.

`.env` must remain ignored by Git.

### 8. Documentation

When adding an important component, update relevant documentation.

Important design decisions should be recorded in:

docs/DECISIONS.md

External sources should be recorded in:

docs/SOURCES.md

Architecture changes should be reflected in:

docs/ARCHITECTURE.md

### 9. Current phase

The project is past MVP: a hosted read-only alpha is live
(https://jobpulse.support, 11 sources, scheduled daily updates, schema v7).
Development remains incremental — one clearly defined sprint at a time.
Current focus: security hardening of the public surface, data-quality depth,
and honest presentation before accounts/AI layers (see docs/ROADMAP.md and
docs/DEPLOYMENT_STATUS.md for the live roadmap).