# Product Vision

## Purpose

Job Market Analyzer is intended to become a job-market intelligence product, not merely a vacancy scraper. It should collect trustworthy source observations, preserve their provenance, turn them into normalized market data, and help people explore which roles, skills, technologies, salaries, and remote-work conditions appear in real vacancies.

The current repository is still an early MVP. Most product capabilities described here are future directions, not existing features.

## Product Principles

### Open-source local product

- The GitHub repository should remain useful to an individual running it locally.
- A user should be able to clone, install, configure, and run the product for personal use.
- Users may customize their own local installation or deployment.
- Local mode remains a first-class use case even if a hosted product is introduced later.
- English is the default language for the product and its documentation.

### Future hosted web product

A future hosted version may provide:

- a visual dashboard and vacancy browser;
- role, skill, salary, geography, and remote-work analytics;
- historical hiring and technology trends;
- personal skill-profile and skill-gap analysis.

None of these hosted capabilities should be presented as implemented until they have been built and verified.

### Multiple interfaces, one core

Future clients may include a web application, REST API, Telegram, Discord, WhatsApp, GitHub integrations, and other interfaces. They should call the same application and domain services rather than reimplement business rules.

Collectors, normalization, deduplication, storage, analytics, and recommendation logic must remain independent from any specific interface.

### Multilingual presentation

- English is the base language.
- Future web and bot interfaces may support a user-selected language.
- Localization should normally remain an interface or presentation concern.
- Raw source content must not be destructively translated or replaced.
- Original text, URLs, source identity, and provenance must remain available.

### Remote-first, not remote-only

Remote work is the main analytical focus, but geography must retain meaningful distinctions between:

- worldwide availability;
- regions and countries;
- cities where relevant;
- timezone restrictions;
- other explicit remote-work restrictions.

The product must not assume that every remote vacancy is available worldwide.

## Intelligence Strategy

### Deterministic first

Prefer deterministic methods where they are reliable:

- database queries and filters;
- same-source identity and deduplication;
- statistics and salary calculations;
- explicit taxonomies and rule-based extraction;
- reproducible market metrics.

Basic collection, browsing, filtering, and analytics must not require an LLM.

### Optional, provider-independent AI

AI may later support enrichment or recommendations where it produces meaningful value. Possible providers include OpenAI-compatible APIs, OpenRouter, DeepSeek, other providers, and user-provided API keys.

The core architecture must not depend permanently on one AI vendor. AI should remain optional where practical, with explicit cost, versioning, provenance, and quality controls.

### Human and AI skill development research

A future research direction may explore how people combine durable knowledge with AI leverage. Possible recommendation categories are:

- **LEARN** — knowledge a user may benefit from developing directly;
- **LEARN + AI** — knowledge that remains important while AI assists execution;
- **AI-LEVERAGED** — work where tools may substantially increase coverage or speed;
- **AUTOMATE** — repetitive work that may be suitable for controlled automation.

These categories require research and validation. They are recommendations, not objective truth or guarantees.

Research may also examine which technologies are useful to learn together, where modern tools or agents can shorten implementation time, and which AI-assisted results a user still needs to understand and verify personally.

A useful working principle is:

```text
GENERATE
-> UNDERSTAND
-> VERIFY
-> DEBUG
```

AI-generated output does not remove the need to understand the result, verify its behavior, and debug failures.

## Recommendation Policy

### Recommendations, not guarantees

The product must never claim that learning a skill, completing a fixed number of projects, or following a roadmap guarantees employment.

Recommendations should expose:

- the relevant market evidence;
- the rationale;
- assumptions and uncertainty;
- the limits of the available source coverage.

Appropriate wording includes “commonly requested,” “appears frequently,” “may improve,” and “could increase opportunity coverage.”

### User autonomy

The product should guide rather than dictate. Users remain free to learn through official documentation, books, courses, YouTube, search engines, AI assistants, experimentation, and open-source projects.

### Portfolio guidance

Future portfolio suggestions may be based on skill combinations found in real vacancies. There is no universal or guaranteed number of projects.

Useful evaluation dimensions may include:

- skill coverage and role relevance;
- project completeness;
- tests and deployment;
- documentation and architecture;
- the user's ability to explain, verify, and debug the work.

Job Market Analyzer itself may serve as one portfolio project for its creator, but that is not a universal assumption for every user.

## Data and Analytics Direction

Future normalized intelligence may cover:

- roles and seniority;
- skills and skill combinations;
- companies and company identity;
- geography and remote restrictions;
- disclosed and derived salary information with explicit provenance;
- hiring trends, vacancy lifecycle, and history.

Analytics should normally count `CanonicalJob` records rather than duplicated source postings. Separate `JobPosting` and raw observations must remain available for source comparison and provenance.

## Future Company Data Interoperability

Company Intelligence / OSINT is a separate future product idea, not a module of the current Job Market Analyzer MVP.

Job Market Analyzer may eventually expose clean company identity through a stable data contract or API. A separate Company Intelligence product could consume that contract and combine lawful public or open-source information such as company profiles, hiring history, technologies, public contacts, and user-defined trust or risk signals.

The products must remain separate domains. The current repository should not prematurely add OSINT tables, invasive surveillance capabilities, or Company Intelligence implementation. It should only avoid choices that would prevent clean future interoperability.

## Privacy, Provenance, and Source Quality

The product should preserve:

- source identity and source-specific semantics;
- original URLs and raw observations;
- attribution and link-back requirements;
- the distinction between observed, normalized, derived, estimated, and AI-generated data.

Original information must not be destroyed solely to simplify analytics. Collection must respect authentication, access restrictions, rate limits, privacy expectations, and applicable source terms.

## Current Non-goals

The current stage does not require:

- a multi-user SaaS system;
- Kubernetes, microservices, or distributed queues;
- AI on every request;
- Telegram, Discord, or WhatsApp interfaces;
- FastAPI or a web frontend;
- migration from SQLite to PostgreSQL;
- Company Intelligence / OSINT implementation.

These are possible future phases, not current MVP requirements.
