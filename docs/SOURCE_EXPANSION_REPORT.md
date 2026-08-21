# Source Expansion Report

Validation date: 2026-08-21

This report records the bounded discovery, implementation, and live validation that
expanded the project from two to six supported vacancy sources. It is evidence from a
small local smoke, not a market-size or source-completeness claim.

## Candidate scorecard

Classification:

- **A — implement now:** credential-free, structured, remote-relevant, and bounded.
- **B — good future source:** technically strong, but needs curated board scope.
- **C — credential required:** stopped before implementation.
- **D — skip:** insufficient contract, brittle HTML/access, or poor incremental value.

| Class | Source | Domain | Access | Auth / cost | Contract | Pagination / stable ID | Remote relevance | Quality / difficulty | Brittleness |
|---|---|---|---|---|---|---|---|---|---|
| A | Himalayas | `himalayas.app` | JSON API | None / free | Official | `limit` + `offset`, max 20 / native `guid` | Remote-only | Good / low-medium | Low; 24-hour cache, attribution and bounded-use terms |
| A | Jobicy | `jobicy.com` | JSON API | None / free | Official | `count` 1–100 / native `id` | Remote-only | Good / low | Low-medium; six-hour delay, polling/republication restrictions |
| A | Remotive | `remotive.com` | JSON API | None / free | Official | Bounded `limit` / native `id` | Remote-only | Medium / low | Low-medium; 24-hour delay, attribution, possible request blocking |
| A | We Work Remotely | `weworkremotely.com` | RSS | None / free | Official | Feed-bounded / native `guid` | Remote-only | Medium / low | Low API risk; feed has stale/duplicate/encoding defects |
| B | Greenhouse | `greenhouse.io` | JSON Job Board API | None for GET / free | Official | Per-board jobs / native job `id` | Mixed per company | High / medium | Low technically; requires curated board tokens and remote filtering |
| B | Lever | `lever.co` | JSON Postings API | None for public GET / free | Official | `skip` + `limit` / native posting `id` | Mixed per company | High / medium | Low technically; requires curated site names/scopes |
| B | Ashby | `ashbyhq.com` | JSON job-board API | None for public GET / free | Official | Board response / native posting ID | Mixed per company | High / medium | Low technically; requires board-name discovery and scope governance |
| C | Adzuna | `adzuna.com` | JSON API | `app_id` + `app_key`; registration | Official | Documented API IDs and paging | Broad, filterable | High / medium | Credential dependency discovered before implementation |
| C | The Muse | `themuse.com` | JSON API | Registered application/API key contract | Official | API paging / native ID | Mixed | Medium-high / medium | Credential and terms dependency discovered before implementation |
| D | Arbeitnow | `arbeitnow.com` | JSON reported by third parties | Apparently none | Insufficient official contract found | Reported paging / reported ID | Remote filter present | Unverified / low | Contract stability and usage terms insufficiently documented |
| D | Remote.co | `remote.co` | HTML | None observed | No public structured contract found | HTML navigation / no verified stable API ID | Remote-only | Medium / high | Scraping and markup brittleness |
| D | Wellfound | `wellfound.com` | Interactive HTML/account flow | Account-oriented | No suitable public vacancy feed verified | Not accepted | Tech/startup remote | Potentially high / high | Access-control and anti-automation risk |
| D | CryptoJobsList / small Web3 boards | Multiple | Mostly HTML/unverified feeds | Varies | No better accepted contract verified | Inconsistent | Web3-focused | Redundant/variable / high | Brittle and overlaps existing Web3.career coverage |

Official research references are recorded in [SOURCES.md](SOURCES.md). No external
repository code was copied.

## Candidate field availability

The following was assessed before selection; “varies” means company/board-dependent.

| Source | Title | Company | Description | Location | Salary | Tags/categories | Application URL | Published time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Himalayas | Yes | Yes | Yes | Yes | Structured when disclosed | Yes | Yes | Yes |
| Jobicy | Yes | Yes | Yes | Yes | Structured when disclosed | Yes | No distinct link | Yes |
| Remotive | Yes | Yes | Yes | Yes | Raw text when disclosed | Yes | No distinct link | Yes |
| We Work Remotely RSS | Yes | Encoded in title | Yes | Yes | No | Yes | No distinct link | Yes |
| Greenhouse | Yes | Board context | Optional full content | Often | Varies | Departments/offices | Yes | Often updated time |
| Lever | Yes | Site context | Yes | Yes | Varies | Categories | Yes | Native creation time varies by output |
| Ashby | Yes | Board context | Yes | Yes | Optional structured compensation | Teams/departments | Yes | Yes |
| Adzuna | Yes | Yes | Yes | Yes | Often | Categories | Yes | Yes |
| The Muse | Yes | Yes | Yes | Yes | Varies | Levels/categories | Yes | Yes |
| Arbeitnow | Reported | Reported | Reported | Reported | Unverified | Reported | Reported | Reported |
| Remote.co | Visible | Visible | Visible page | Visible | Varies | Page categories | Visible | Varies |
| Wellfound | Visible/account-dependent | Visible | Account/page-dependent | Visible | Often ranges | Tags | Account/page-dependent | Varies |
| Small Web3 boards | Varies | Varies | Varies | Varies | Varies | Varies | Varies | Varies |

## Selected and implemented sources

Four credential-free, remote-wide sources were selected: Himalayas, Jobicy,
Remotive, and We Work Remotely RSS. They add JSON and RSS diversity while staying
within the existing collector → `RawJob` → normalizer → generic collection service →
`SQLiteJobRepository` pipeline. A source registry and generic scraping framework were
not added because four small adapters do not justify that extra boundary yet.

### Identity and field mapping

| Provider | `source_scope` | Native `external_id` | Source/application URLs | Important normalized fields |
|---|---|---|---|---|
| `himalayas` | `global` | `guid` | `guid` / `applicationLink` | title, company, HTML description, location/timezones, type, categories, structured salary, epoch publication |
| `jobicy` | `global` | `id` | `url` / `None` | title, company, HTML description, region, type, industries, structured salary, ISO publication |
| `remotive` | `global` | `id` | attributed `url` / `None` | title, company, HTML description, candidate region, type, category/tags, raw salary text, publication time |
| `we_work_remotely` | `global` | RSS `guid` | RSS `link` / `None` | company/title, HTML description, region/country/state, type, category/skills, RFC publication |

Unknown optional fields remain `None`/empty. No salary parser, inferred currency,
source-specific persistence SQL, or fuzzy canonical linking was introduced.

## Offline tests

There are 41 new-source-focused tests:

- 12 collector tests: valid payloads, native identity, paging/limits, malformed-item
  continuation, invalid feed shapes, and network error propagation;
- 25 normalizer cases: identity/URL validation, missing optional description,
  location and salary, HTML conversion, tags, employment type, salary provenance,
  and timestamp validation;
- 4 parametrized integration cases exercising each source through the real generic
  collection service and SQLite repository twice.

Normal `pytest` uses mocked transports/minimal payloads and performs no live request.
All collectors have explicit HTTP timeouts and a project User-Agent. No source uses a
secret, cookie, authorization header, or environment credential.
The existing HTTP architecture has no shared retry policy, so these bounded manual
commands make no hidden retries: network/systemic failures propagate clearly instead
of multiplying public requests.

## Live collection evidence

Each command was bounded and executed twice against an ignored source-specific
SQLite database. “Persisted” is the number of valid unique observations passed to the
generic repository; “Fetched” includes exact repeated feed items.

| Source | Run | Fetched | Persisted | Postings created | Raw observations created | Failed |
|---|---:|---:|---:|---:|---:|---:|
| Himalayas | 1 | 60 | 52 | 52 | 52 | 0 |
| Himalayas | 2 | 60 | 52 | 0 | 0 | 0 |
| Jobicy | 1 | 50 | 50 | 50 | 50 | 0 |
| Jobicy | 2 | 50 | 50 | 0 | 0 | 0 |
| Remotive | 1 | 18 | 18 | 18 | 18 | 0 |
| Remotive | 2 | 18 | 18 | 0 | 0 | 0 |
| We Work Remotely | 1 | 99 | 98 | 98 | 98 | 0 |
| We Work Remotely | 2 | 99 | 98 | 0 | 0 | 0 |

Himalayas pages overlapped by eight `guid` values. WWR emitted one `guid` twice with
different location text. The collectors now use deterministic first-observation wins
within one response, so response-level duplicates do not overwrite each other or
create unstable raw history. The second run for every source was fully idempotent.

The four live databases contain 218 new canonical jobs, 218 postings, and 218 initial
raw observations in total. Including the existing 100-record Remote OK and
100-record Web3.career smoke databases, the local validation corpus represents 418
source postings. This is not a unique-market count because cross-source linking is
not complete.

## Database integrity

| Source DB | `user_version` | `foreign_key_check` | Canonical | Postings | Raw |
|---|---:|---|---:|---:|---:|
| Himalayas | 3 | Empty | 52 | 52 | 52 |
| Jobicy | 3 | Empty | 50 | 50 | 50 |
| Remotive | 3 | Empty | 18 | 18 | 18 |
| We Work Remotely | 3 | Empty | 98 | 98 | 98 |

All four databases initialized current skill/role intelligence tables. The optional
bounded analysis added derived rows only; it did not change vacancy counts or source
provenance.

## Data-quality assessment

| Source | Score | Company / description | Location | Application | Duplicate/staleness/encoding notes |
|---|---|---|---|---|---|
| Himalayas | GOOD | 52/52 / 52/52 | 50/52 | 52/52 | Eight overlapping page items; one unusual prefixed title observed |
| Jobicy | GOOD | 50/50 / 50/50 | 50/50 | No distinct direct link | No exact native-ID duplicates in sample; documented six-hour delay |
| Remotive | MEDIUM | 18/18 / 18/18 | 18/18 | No distinct direct link | Small response; includes task/gig-style listings; documented 24-hour delay |
| We Work Remotely | MEDIUM | 98/98 / 98/98 | 98/98 | No distinct direct link | One duplicate GUID, replacement characters, and a 2023 timestamp in current RSS |

Published-time ranges observed were:

- Himalayas: 2026-08-21 12:23:47Z through 12:40:15Z;
- Jobicy: 2026-08-20 19:46:55Z through 2026-08-21 09:28:56Z;
- Remotive: 2026-07-23 15:37:35Z through 2026-08-20 09:54:55Z;
- WWR: 2023-02-07 20:07:41Z through 2026-08-21 10:40:25Z.

No lifecycle/expiry inference was added merely to hide stale source data.

## Salary and source-tag comparison

| Source | Salary present | Semantics | Tags present |
|---|---:|---|---:|
| Himalayas | 27/52 | Source-provided min/max/currency/period | 52/52 |
| Jobicy | 30/50 | Source-provided min/max/currency/period | 50/50 |
| Remotive | 13/18 | Unparsed source salary string only | 18/18 |
| We Work Remotely | 0/98 | Not supplied in RSS | 98/98 |

Source tags are observed provider metadata, not canonical skills. Granularity varies
substantially and some composite WWR strings are unsuitable for direct taxonomy use.

## Cross-source duplicate signal

No exact normalized company+title pair repeated among the four new sources alone.
Across the complete six-source smoke corpus, one strong exact example was found:

- `Lemon.io — Senior Data Engineer` appears separately in Remote OK and Remotive.

A likely near-match also exists for `TELUS Digital — Content Reviewer - United
States/US` in Remotive and WWR. Other same-company similar engineering titles, such
as Coinbase roles, are not safe duplicate evidence because their functional scopes
differ. All records remain separate `JobPosting` rows and were not silently merged.

## Optional intelligence compatibility smoke

The first 20 deterministic postings per source (all 18 for Remotive) were analyzed:

| Source | Skill coverage | Role coverage | Failures |
|---|---:|---:|---:|
| Himalayas | 7/20 (35.0%) | 5/20 (25.0%) | 0 |
| Jobicy | 6/20 (30.0%) | 5/20 (25.0%) | 0 |
| Remotive | 9/18 (50.0%) | 4/18 (22.2%) | 0 |
| We Work Remotely | 11/20 (55.0%) | 5/20 (25.0%) | 0 |

No normalization incompatibility was found. Coverage reflects a small mixed-role
sample and conservative taxonomies, not source quality. Some source tags (for example
Remotive's bare `go`) can carry ambiguous provider semantics; raw/direct evidence
remains inspectable and no taxonomy was expanded in this sprint.

## Limitations and recommended next sources

- Public aggregator feeds can overlap and include delayed, stale, or low-value jobs.
- No vacancy-expiry lifecycle or complete cross-source canonical linker exists.
- Application links are unavailable in three of four new public feeds.
- Salary coverage and semantics differ; no salary normalization was attempted.
- RSS replacement characters are source-side and remain visible.
- The adapters intentionally collect only bounded samples, not complete archives.

The next source milestone should be a curated ATS pilot: add a small configuration of
specific remote-friendly Greenhouse boards first, then Lever and Ashby. Board scope
must be explicit in `source_scope`; broad board discovery should not become an
unbounded crawler.

## Shortest route to the first personal web dashboard

Avoid another long invisible infrastructure sequence:

1. add a small read-only analytics/query layer over current SQLite (source counts,
   role/skill frequencies, vacancies, and transparent duplicate limitations);
2. expose only those stable queries through a local backend API;
3. build dashboard v0 with source health, vacancy browser, and role/skill summaries.

Salary and seniority do **not** block dashboard v0. They should appear as unavailable
or raw/provenance-aware fields until their contracts are ready, then be added as
incremental dashboard slices. PostgreSQL is also not required for a first local
single-user dashboard.
