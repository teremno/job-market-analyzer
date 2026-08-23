# External Sources and Attribution

This document records external repositories, APIs, datasets, articles, and architectural references used during development.

We document external sources even when only an architectural idea or source list is reused.

---

## Source Template

### Source Name

URL:

License:

Used for:

- [ ] Code
- [ ] Architecture
- [ ] Dataset
- [ ] API discovery
- [ ] Source discovery
- [ ] General inspiration

What was used:

Notes:

---

## Active Vacancy Sources

### Optional publication-date validation policy

Publication time is optional normalized data, but each adapter keeps the validation
semantics established for its source contract. Remote OK, Himalayas, Jobicy,
Remotive, and We Work Remotely accept an absent publication value but reject that
individual posting when a supplied value has the wrong type, format, timezone, or
range. The generic collection service records the item failure and continues with
other source items.

Web3.career is intentionally more tolerant because its API exposes three observed
date candidates: it selects the first safely parsed value from `date`, `postedAt`,
and `date_epoch`, skipping malformed candidates; if none is valid, `published_at`
remains empty. This source-specific difference is retained for the current MVP.
Changing it would alter accepted observations and normalized `content_hash` history,
so any future standardization needs an explicit migration/versioning decision rather
than a housekeeping edit.

### Remote OK

Official JSON API:
https://remoteok.com/api

Remote OK also advertises a public RSS feed, but the MVP integration uses only the JSON API.

Authentication:
None.

Attribution requirements:

- identify Remote OK as the source;
- preserve and expose the original Remote OK job URL;
- link back to Remote OK according to the legal notice embedded in the API response;
- do not use the Remote OK logo without written permission.

MVP source identity:

- `source_provider = "remote_ok"`;
- `source_scope = "global"`;
- `external_id` uses the source-native `id` field.

Fields currently used:

- `id`;
- `url`;
- `apply_url` when it is distinct from the Remote OK job URL;
- `position`;
- `company`;
- `description`;
- `location`;
- `tags` for conservative employment-type normalization;
- `date`, with `epoch` as a fallback for publication time.

Remote OK `salary_min` and `salary_max` remain preserved in the raw payload but are not normalized yet because the feed does not provide enough reliable currency and period context. The first array item may contain feed metadata and legal terms rather than a vacancy; the collector recognizes it as metadata and does not count it as a job.

No Remote OK code was copied. The integration was implemented against the public feed structure and its embedded attribution terms.

---

### Web3.career

Official API landing page:
https://web3.career/web3-jobs-api

Official API reference:
https://docs.bondex.app/api-reference

JSON endpoint:
https://web3.career/api/v1

Authentication:

- every request requires an API token in the `token` query parameter;
- the collector reads it from `WEB3_CAREER_API_TOKEN`;
- tokens must not be committed, logged, or exposed in client-side code;
- HTTPX query-token log redaction is installed before each request because INFO-level HTTPX logs otherwise include the full URL;
- free API access is requested through the official API landing page;
- the API documents `429` responses when its rate limit is exceeded.

Attribution and link-back requirements:

- identify Web3.career as the source;
- use the unmodified `apply_url` when directing users to a job;
- use a follow link (`rel="follow"` or no `rel` attribute);
- do not use `rel="nofollow"`;
- do not append tracking parameters to `apply_url`.

MVP source identity:

- `source_provider = "web3_career"`;
- `source_scope = "global"`;
- `external_id` uses only the source-native `id` field;
- `RawJob.source_url` preserves `url` when the API supplies a valid non-empty value;
- the live API may omit `url`, and a missing or null value does not invalidate the vacancy;
- no posting URL is synthesized from `id`, and `apply_url` is not copied into `source_url`;
- normalized `application_url` preserves the required, unmodified user-facing `apply_url` used for attribution and application.

Fields currently used:

- `id`;
- optional `url`, when supplied;
- required `apply_url`;
- `title`;
- `company`;
- `location`, with `city` and `country` as a fallback;
- `remote` or `is_remote` when explicitly boolean;
- `description` through the shared safe HTML-to-text converter;
- `tags`, preserved only in the original raw payload for later analysis;
- the first safely parsed value from `date`, `postedAt`, then `date_epoch`;
- disclosed `salary` text.

Salary distinction policy:

- only the officially documented `salary` field populates normalized `salary_text`;
- `salary_min_value`, `salary_max_value`, `salary_currency`, and `salary_unit` remain only in the original `RawJob.payload` until their provenance is documented explicitly;
- `estimated_min_salary`, `estimated_max_salary`, and `estimated_avg_salary` also remain raw-only and are not represented as employer-declared salary;
- normalized structured salary fields remain empty; salary text is not parsed into invented numbers, currency, or period.

The API currently returns a mixed top-level JSON array, normally with metadata strings and a nested jobs array. The collector searches for that nested array and also supports the documented direct-array fallback. The integration uses only the official JSON API and does not scrape Web3.career HTML listing pages.

No Web3.career or Bondex code was copied. The integration was implemented from the official API contract and terms.

---

### Himalayas

Official API documentation and OpenAPI contract:
https://himalayas.app/docs/remote-jobs-api

JSON endpoint:
https://himalayas.app/jobs/api

Status: implemented, offline-tested, and live-validated twice on 2026-08-21.

Authentication and cost: none. The documented public feed is free, cached for 24
hours, limited to 20 jobs per request, and supports `limit`/`offset` pagination. The
collector deliberately requests at most three pages (60 feed items).

Attribution: identify Himalayas as the source and link to Himalayas. The integration
preserves the source-native `guid`, which is also the public job URL.

MVP identity:

- `source_provider = "himalayas"`;
- `source_scope = "global"`;
- `external_id = guid` (source-native stable URL identifier).

Normalized fields include title, company, HTML description, location and timezone
restrictions, employment type, categories and parent categories, explicit structured
salary fields, publication epoch, source URL, and `applicationLink` when present.
The normalizer does not parse or invent salary. Overlapping pages can repeat an exact
`guid`; the bounded collector keeps the first observation from that response and
reports the skipped duplicate count in collection metadata.

Live limitation: two of 52 validated postings lacked a location restriction. All 52
had descriptions, company names, and source tags; 27 carried structured salary data.

No Himalayas code was copied. The adapter was independently implemented from the
documented response contract and validated public responses.

---

### Jobicy

Official API documentation:
https://github.com/Jobicy/remote-jobs-api

JSON endpoint:
https://jobicy.com/api/v2/remote-jobs

Status: implemented, offline-tested, and live-validated twice on 2026-08-21.

Authentication and cost: none. The documented `count` parameter supports 1вЂ“100
records. Jobicy says API jobs are delayed by six hours, recommends polling no more
than hourly, and restricts bulk republishing/resale; this project performs only one
bounded request per manual command.

Attribution: preserve the Jobicy job URL and identify Jobicy as the source when
displaying its feed content.

MVP identity:

- `source_provider = "jobicy"`;
- `source_scope = "global"`;
- `external_id` uses the source-native `id`.

Normalized fields include job title, company, HTML description, geographic region,
job type, industry categories, explicit structured salary, publication timestamp,
and Jobicy source URL. The public response does not expose a distinct verified direct
application URL, so `application_url` remains `None` rather than copying the
aggregator URL.

Live limitation: all 50 validated records were complete for title, company,
description, location, and tags, but none exposed a separate application link.
Thirty carried structured salary data.

No Jobicy code was copied. The adapter was independently implemented from its public
API documentation and observed response contract.

---

### Remotive

Official public API documentation and terms:
https://remotive.com/remote-jobs/api

JSON endpoint:
https://remotive.com/api/remote-jobs

Status: implemented, offline-tested, and live-validated twice on 2026-08-21.

Authentication and cost: none. The manual collector makes one request with a bounded
`limit`. Remotive states that public API jobs are delayed by 24 hours and that
excessive requests may be blocked.

Attribution requirements: credit Remotive as the source and link back to the exact
Remotive job URL. The adapter preserves that URL as `source_url` and never substitutes
an unattributed destination.

MVP identity:

- `source_provider = "remotive"`;
- `source_scope = "global"`;
- `external_id` uses the source-native `id`.

Normalized fields include title, company, HTML description, candidate location,
category and tags, job type, raw disclosed salary text, publication timestamp, and
the attributed Remotive URL. Salary strings are deliberately not parsed into numbers,
currency, or period. A separate verified application URL is not present in the feed.

Live limitation: the bounded API response contained only 18 records despite a limit
of 50. All 18 had company, description, location, and tags; 13 had non-empty salary
text. The sample included some task/gig-style records alongside ordinary vacancies.

No Remotive code was copied. The adapter was independently implemented from the
official public API contract and terms.

---

### We Work Remotely

Official RSS documentation:
https://weworkremotely.com/remote-job-rss-feed

Official RSS endpoint:
https://weworkremotely.com/remote-jobs.rss

Status: implemented, offline-tested, and live-validated twice on 2026-08-21.

Authentication and cost: none for RSS. WWR's separate write/posting API requires a
special token and is not used: https://weworkremotely.com/api

Attribution requirements: identify We Work Remotely as the source and preserve the
original WWR job link. The integration consumes only the official RSS document and
does not scrape linked pages.

MVP identity:

- `source_provider = "we_work_remotely"`;
- `source_scope = "global"`;
- `external_id` uses the RSS `guid`.

Normalized fields include the company/title pair encoded in RSS `title`, HTML
description, region/country/state, category and skills text, employment type,
publication timestamp, and WWR source URL. RSS provides neither structured salary nor
a separate application URL, so those fields remain empty.

Live limitations: the feed returned 99 items but one duplicate `guid`; the collector
kept 98 unique observations. It also contained replacement characters in some text
and at least one very stale posting timestamp (2023-02-07). Source-side category and
skills strings vary in granularity. These issues are preserved and documented rather
than silently corrected.

No WWR code was copied. The adapter was independently implemented against the
official RSS contract.

### Greenhouse Job Boards

Official API documentation:
https://developers.greenhouse.io/job-board.html

JSON endpoint per board:
https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

Status: implemented and offline-tested; first live curated-board validation
recorded in this document's history.

Authentication and cost: none. Each board is one public, credential-free JSON
GET request returning every currently listed posting including full HTML
content when `content=true`. The collector performs exactly one request per
configured board token per run.

Attribution: identify the company board via Greenhouse as the source and link
to the original `absolute_url`, which is preserved as both `source_url` and
`application_url`.

MVP identity:

- `source_provider = "greenhouse"`;
- `source_scope` = the lowercase company board token (for example `coinbase`);
- `external_id` uses the source-native numeric `id`.

Curated boards (25): affirm, gusto, cockroachlabs, coinbase, ripple, fireblocks, gemini, bitgo, consensys,
recordedfuture, gitlab, canonical, cloudflare, datadog, elastic, grafanalabs,
chainguard, duolingo, coursera, stripe, figma, discord, dropbox, twilio,
robinhood. (Order in file mirrors registry; see GREENHOUSE_BOARD_TOKENS.)

Normalized fields include title, company name, HTML description through the
shared safe converter, location name, `first_published` as publication time,
`updated_at` as source-updated time, department/office names as structured
source tags, and the original board URL for application. A failed board is an
isolated collection result while later boards continue; only all boards failing
is a systemic error. No salary or remote-scope inference is performed: Greenhouse
boards mix onsite, hybrid, and remote postings, so `remote_scope` stays unset
until a dedicated geography analyzer exists.

No Greenhouse code was copied. The adapter was independently implemented from
the official documented API contract.

### Lever Job Boards

Official API documentation:
https://github.com/lever/postings-api

JSON endpoint per board:
https://api.lever.co/v0/postings/{board_token}?mode=json

Status: implemented, offline-tested, and live-validated.

Authentication and cost: none. Each board is one public credential-free JSON
GET request returning every currently listed posting. The collector performs
exactly one request per configured board token per run.

Attribution: identify the company Lever board as the source and preserve the
original `hostedUrl`; the documented `applyUrl` is used unmodified as the
application link.

MVP identity:

- `source_provider = "lever"`;
- `source_scope` = the lowercase company board token;
- `external_id` uses the source-native `id`.

Curated pilot boards: spotify, palantir.

Normalized fields include title, plain-text description, location,
`categories.commitment` mapped conservatively onto employment types, structured
`workplaceType` mapped onto the remote flag (hybrid/onsite are not remote),
epoch-millisecond `createdAt` as publication time, and department/team names as
structured source tags. Company name is not exposed by this endpoint and stays
empty rather than being derived from the board token. No salary is normalized.
A failed board is an isolated result while later boards continue; all boards
failing is systemic.

No Lever code was copied; the adapter was implemented from the public API
contract.

---

### Ashby Job Boards

Official API documentation:
https://developers.ashbyhq.com/docs/public-job-posting-api

JSON endpoint per board:
https://api.ashbyhq.com/posting-api/job-board/{board_token}

Status: implemented, offline-tested, and live-validated.

Authentication and cost: none. Each board is one public credential-free JSON
GET request returning listed postings. The collector performs exactly one
request per configured board token per run with `includeCompensation=true`:
the first structured Salary component populates normalized salary bounds,
currency, and period; equity-only structures yield no salary fields.

Attribution: identify the company Ashby board as the source and preserve the
original `jobUrl`; `applyUrl` is used unmodified.

MVP identity:

- `source_provider = "ashby"`;
- `source_scope` = the lowercase company board token;
- `external_id` uses the source-native `id`.

Curated boards (24): openai, elevenlabs, clickhouse, cohere, ramp, notion,
langchain, perplexity, baseten, replit, fireworks, supabase, temporal, sentry,
sardine, linear, modal, posthog, cerebras, cognition, suno, vanta,
attio, warp.

Normalized fields include title, description with a plain-text preference and
safe HTML fallback, location, boolean `isRemote`, employment type mapped
conservatively, ISO `publishedAt` as publication time, and department/team
names as structured source tags. Company name is not part of the job payload
and stays empty. No salary or remote-scope geography inference is performed.
A failed board is an isolated result while later boards continue.

No Ashby code was copied; the adapter was implemented from the official
documented contract.

---

## Researched Sources Not Implemented

### Good future sources

- **Greenhouse additional boards** вЂ” the adapter is source-scope driven, so new
  company boards are one-token additions to `GREENHOUSE_BOARD_TOKENS`.
- **Lever and Ashby additional boards** вЂ” new company boards are one-token
  additions to `LEVER_BOARD_TOKENS` or `ASHBY_BOARD_TOKENS`.

### Credential required вЂ” not implemented

- **Adzuna** вЂ” requires registered `app_id` and `app_key`:
  https://developer.adzuna.com/overview.
- **The Muse** вЂ” its developer contract requires application registration/API-key
  usage for a production integration: https://www.themuse.com/developers/api/v2 and
  https://www.themuse.com/developers/api/v2/terms.

### Skipped or brittle

- **Arbeitnow** вЂ” a JSON endpoint is referenced by third parties, but no sufficiently
  strong official API contract was found for a durable adapter.
- **Remote.co** вЂ” HTML-oriented listing pages without a documented structured public
  vacancy API; skipped to avoid a brittle scraper.
- **Wellfound** вЂ” account/interactive HTML-oriented access and anti-automation risk;
  skipped rather than bypassing controls.
- **CryptoJobsList and other small Web3 boards** вЂ” no better credential-free,
  documented broad feed was verified in this sprint; avoid duplicating Web3.career
  through brittle HTML extraction.

The complete candidate scorecard and live evidence are in
[Source Expansion Report](SOURCE_EXPANSION_REPORT.md).

---

## Candidate Repositories

### ever-jobs / ever-jobs

URL:
https://github.com/ever-jobs/ever-jobs

Status:
Candidate for evaluation.

Potential use:

- multi-source collector architecture
- job source discovery
- normalized job schemas
- API/RSS integration ideas

No code has been copied at this stage.

---

### Feashliaa / job-board-aggregator

URL:
https://github.com/Feashliaa/job-board-aggregator

Status:
Candidate for evaluation.

Potential use:

- ATS job collection
- Greenhouse
- Lever
- Ashby
- Workday
- large-scale company/job discovery

No code has been copied at this stage.

---

### speedyapply / JobSpy

URL:
https://github.com/speedyapply/JobSpy

Status:
Candidate for evaluation.

Potential use:

- job-board extraction reference
- LinkedIn / Indeed / Glassdoor coverage

No code has been copied at this stage.

---

## Rule

Before copying or adapting code from an external repository:

1. Check its license.
2. Record the repository here.
3. Record the files or concepts used.
4. Preserve any attribution required by the license.
5. Prefer adapting ideas over copying large code sections when practical.
