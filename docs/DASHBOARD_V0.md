# Dashboard v0

Status: implemented and locally browser-validated; awaiting commit checkpoint.

## Scope

Dashboard v0 is the first browser-visible personal product in Job Market Analyzer.
It reads one existing SQLite dataset through the local read-only FastAPI adapter. It
does not collect, analyze, migrate, or mutate data from the browser.

All counts are **source-posting counts**. They must not be interpreted as globally
unique vacancies because automatic cross-source canonical linking is incomplete.
Skill evidence means mentioned in a posting, not necessarily required. Source
freshness describes this local dataset, not source uptime or reliability.

## Pages

- **Overview** — source-posting and source counts, role/skill analysis coverage,
  top observed roles and skills, and postings by source.
- **Jobs** — title/company search, source/role/skill selectors, combined URL-backed
  filters, 25-row offset pagination, bounded role/skill badges, and safe source/apply
  links.
- **Roles** — all observed role codes and posting counts; detail pages show skills
  mentioned in classified postings and representative postings.
- **Skills** — all observed skill codes and posting counts; detail pages show
  associated roles, frequently co-mentioned skills, and representative postings.
- **Sources** — posting count, newest published date, latest observed posting, and
  three-state role/skill analysis coverage for each provider.

## Frontend architecture

The frontend lives in `web/` and remains independent from the Python package. It uses
Next.js App Router, React, TypeScript, server components for read operations, one
small client navigation component, native URL query parameters, semantic HTML, and
global CSS. There is no state framework, chart library, component suite, proxy,
frontend API route, or duplicated analytics logic.

`web/src/lib/api.ts` is the typed HTTP boundary. Every fetch is read-only, uncached,
and has a fifteen-second timeout. Lightweight runtime guards reject malformed JSON
shapes. Expected API/network failures become explicit product states; unexpected
render errors remain eligible for framework error boundaries.

The Jobs page requests `GET /api/overview?top_limit=100` to obtain every observed
role and skill without loading every posting or copying backend taxonomy metadata.
The parameter is bounded by the API to 1–100 and defaults to 10 for ordinary overview
use.

## Local startup

From the repository root in Windows PowerShell, start the backend:

```powershell
job-market-analyzer serve --database .\job-market.sqlite3
```

In a second PowerShell window:

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

The default API base is `http://127.0.0.1:8000`. To override it, copy
`web/.env.example` to `web/.env.local` and set:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

There are no frontend secrets. Never put `WEB3_CAREER_API_TOKEN`, a database path, or
another credential in a `NEXT_PUBLIC_` variable.

## Unified personal database

Run every collector against the same path, then both deterministic analyzers:

```powershell
job-market-analyzer collect-remote-ok --database .\job-market.sqlite3
job-market-analyzer collect-web3-career --database .\job-market.sqlite3
job-market-analyzer collect-himalayas --database .\job-market.sqlite3
job-market-analyzer collect-jobicy --database .\job-market.sqlite3
job-market-analyzer collect-remotive --database .\job-market.sqlite3
job-market-analyzer collect-we-work-remotely --database .\job-market.sqlite3
job-market-analyzer analyze-skills --database .\job-market.sqlite3 --limit 10000
job-market-analyzer analyze-roles --database .\job-market.sqlite3 --limit 10000
```

The Web3.career collector reads its existing token only from
`WEB3_CAREER_API_TOKEN`. Collection performs network requests; analysis, serving, and
dashboard browsing are local.

## Development checks

```powershell
cd web
npm run lint
npm run typecheck
npm run build
```

If the dashboard says **Backend unavailable**, start the API using the exact database
path above and refresh. If the API refuses startup, confirm that the file exists and
uses the current schema. If selectors are empty, run the relevant analyzers against
the same database used by `serve`.

## Known limitations

- No complete cross-source canonical deduplication.
- Salary, seniority, and remote-geography intelligence is exposed through the
  API and dashboard v2 surfaces; counts stay posting-level and mention-level.
- Search is the API's bounded SQLite title/company substring search.
- Pagination is offset-based and fixed at 25 postings per dashboard page.
- Role and skill taxonomies are conservative, English-oriented, and may classify a
  posting as Unknown or analyzed-zero.
- The product is local-only: no accounts, saved searches, favorites, deployment, or
  write endpoints.

## Personal-use product audit

After the first unified launch, inspect real results rather than choosing the next
backend feature in advance:

- Are title/company search results useful?
- Are role classifications believable, and which real postings become Unknown?
- Which important mentioned skills are absent from extraction?
- Are stale postings visible?
- Are duplicate real jobs visible across sources?
- Which sources look noisy or low-value?
- Which salary formats appear in real source postings?
- Which geography restrictions matter during actual browsing?
- Which missing feature blocks personal use most?

Use those observations to prioritize data-quality fixes, then seniority, salary,
geography, or cross-source linking according to demonstrated impact.
