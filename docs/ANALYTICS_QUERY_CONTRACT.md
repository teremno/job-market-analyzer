# Internal Analytics Query Contract

Status: Dashboard v0 read-only contract, 2026-08-21.

## Purpose and boundary

The internal analytics layer answers the minimum product questions required by the
first personal dashboard. It reads `job_postings`, active compatible role runs, and
active compatible skill runs. It does not collect jobs, mutate source or intelligence
rows, expose raw payloads, implement HTTP, or format presentation-specific output.

`AnalyticsRepository` is the storage-independent query boundary.
`SQLiteAnalyticsRepository` is its current direct-SQL implementation. A separate
service was deliberately not added because there is no application policy beyond the
query contract yet; a future local API can depend on `AnalyticsRepository` directly.

## Counting contract

Dashboard v0 counts are **posting-level**:

- `posting_count` means one durable `job_postings` row;
- every role and skill aggregate uses distinct posting IDs, never evidence-row count;
- source postings are not described as globally unique real-world vacancies;
- no fuzzy cross-source linking is performed.

`canonical_job_id` is exposed on list items for provenance/future grouping, but the
overview deliberately does not present a “deduplicated market count.” Existing
canonical groups are incomplete because automatic cross-source linking is incomplete.

## Exact-current intelligence resolution

A role run is current only when all of these match:

1. `analyzer_kind = "roles"`;
2. `taxonomy_version = ROLE_TAXONOMY_VERSION`;
3. `extractor_version = ROLE_TAXONOMY_VERSION` under the current analyzer contract;
4. `input_hash = calculate_role_input_hash(current title, current description)`.

A skill run uses the equivalent active Skill Taxonomy v2 identity and
`calculate_skill_input_hash(current title, current description, current normalized
source_tags)`.

The SQLite implementation registers those existing deterministic hash functions as
connection-local SQLite functions and resolves exact compatible identities in SQL.
It never selects `MAX(created_at)`. Therefore:

- a historical older-version run is excluded;
- a once-current run becomes unavailable when analyzer input changes;
- recomputation history can coexist without contaminating current analytics;
- a posting without an exact active run is `not_analyzed`.

## Analysis states

Both role and skill list projections use only three states:

- `not_analyzed`: no exact active-version/current-input run;
- `analyzed_zero`: exact run exists with zero corresponding evidence rows;
- `analyzed_with_results`: exact run exists with at least one evidence row.

For roles, `analyzed_zero` is Unknown. For skills, it means the active extractor found
zero mentioned skills. Neither state proves that the real vacancy lacks a role or
skill.

## Query models

All DTOs are immutable dataclasses with slots. No `sqlite3.Row`, connection, full
description, or raw payload crosses the repository boundary.

- `AnalyticsOverview`: posting/source counts, three-state role/skill counts, source
  counts, top roles, and top skills.
- `PostingSearchFilters`: source, role code, skill code, and optional text.
- `PostingListItem`: bounded source identity, canonical ID, title/company/location,
  timestamps/URLs, current statuses, roles, and skills.
- `PagedPostings`: stable offset page plus total `posting_count`.
- `RoleDetail`: role identity, posting count, skills mentioned among matching
  postings, and representative postings.
- `SkillDetail`: skill identity, posting count, associated current roles,
  co-occurring skills, and representative postings.
- `SourceSummary`: observed posting/freshness and current classification coverage.

Role and skill codes are language-neutral query identity. English names are default
display labels from the active taxonomy and may later be replaced by UI translations
without changing filters or counts.

## Overview

`get_overview(top_limit=10)` returns:

- current posting and provider counts;
- role classified, role Unknown, and role not-analyzed posting counts;
- skill-with-results, skill-zero, and skill-not-analyzed posting counts;
- postings by provider;
- top roles and skills by distinct postings.

Aggregate limits must be between 1 and 100. Ties use machine code ascending.

## Current posting list

`list_postings(filters, limit=50, offset=0, include_stale=False)` supports:

- exact `source_provider`;
- exact active `role_code`;
- exact active `skill_code`;
- combined role and skill intersection;
- literal title/company substring search.

By default the list and every aggregate consider only active postings: rows whose
`last_seen_at` is within `ACTIVE_POSTING_WINDOW_DAYS = 30` of the repository clock.
The clock is injectable (`now_provider`) for deterministic tests. Stale postings
stay stored but leave default views; `include_stale=True` restores them for history
access.

All values are SQL parameters. `%`, `_`, and the escape character in search input are
escaped and treated literally. SQLite `LIKE ... COLLATE NOCASE` provides a simple
ASCII-oriented case-insensitive MVP search. It is intentionally not FTS and may scan
the current posting table. The page limit is 1–100 and offset is non-negative.

Ordering is stable:

1. non-null `published_at` before null;
2. `published_at DESC`;
3. `last_seen_at DESC`;
4. `source_provider`, `source_scope`, `external_id`, and posting `id` ascending.

List results use a fixed number of batch queries, not one query per posting. Page run
IDs are hash-validated again while loading evidence so a concurrent posting change
cannot turn stale evidence into a current result.

## Role detail

`get_role_detail(role_code)` returns zero or more distinct matching postings and the
skills mentioned by exact current skill runs among those postings. These are
**mentioned skills among postings classified as the role**, not required skills.
Unknown role codes return `None`; an active role with no matches returns a zero-count
detail.

## Skill detail

`get_skill_detail(skill_code)` returns:

- distinct postings mentioning the skill;
- current roles on those postings;
- other current skills co-occurring on those postings;
- representative current postings.

The selected skill is excluded from co-occurrence and repeated evidence fields count
only once per posting. Unknown skill codes return `None`.

## Source summary

`list_source_summaries()` returns, per provider:

- posting count;
- newest available `published_at`;
- newest `last_seen_at`;
- counts for all three role and skill states;
- percentages with role results and extracted skill results.

This describes the persisted dataset. It is not collector uptime, source reliability,
market share, or proof of global representativeness.

## Read-only and performance decisions

The repository executes only bounded/aggregate `SELECT` statements and registers two
connection-local deterministic functions. Representative tests compare serialized
database bytes and `total_changes` before and after every public query family.

On the development machine, a deterministic dense fixture with current role and
skill runs for every posting produced these three-run medians:

- at 1,000 postings: 3–81 ms across overview, list, combined filtered list, role
  detail, skill detail, and source summary queries;
- at 10,000 postings: 33 ms for a selective combined filter, 0.40–0.43 seconds for
  source/list queries, and 0.99–1.22 seconds for aggregate/detail queries whose
  selected role or skill matched every posting (observed maximum: 1.30 seconds).

These are local sanity measurements, not service-level guarantees. The current
schema's primary, unique analysis identity, and evidence indexes are reused. No schema
version or index was added: exact-current hash validation, list ordering, and
leading-wildcard text search can still scan/sort 10,000 rows, but measured local
behavior remains usable for a personal Dashboard v0 and does not yet justify a
migration. Reassess with the unified real database and actual API latency targets
before adding a covering index, materialization, or FTS.

## Product limitations

- Results are limited to collected sources and current analyzed inputs.
- Counts are posting-level and not fully cross-source deduplicated.
- Mentioned skills are not necessarily required skills.
- Role/skill taxonomies remain conservative and English-oriented.
- No normalized seniority, salary, or geography is required for Dashboard v0.
- No claim of global job-market representativeness is made.

## Current API mapping

The local read-only API maps this contract without duplicating analytics logic:

- `GET /api/overview` → `get_overview()`;
- `GET /api/jobs` → `list_postings()`;
- `GET /api/roles/{code}` → `get_role_detail()`;
- `GET /api/skills/{code}` → `get_skill_detail()`;
- `GET /api/sources` → `list_source_summaries()`.

The local API should add request validation, response schemas, timeouts, and explicit
database connection lifecycle. It must not reimplement SQL or current-run selection.
