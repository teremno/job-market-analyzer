# Data Quality Notes

This document records concrete data-quality observations from real personal-use
dataset runs. Numbers are point-in-time audit snapshots, not stable product
metrics. They exist to drive the next vertical sprints, especially Job
Lifecycle v1 and future taxonomy revisions.

---

## Audit 2026-08-22 — first real six-source guided update

Command: `job-market-analyzer update --database .\job-market.sqlite3` against the
existing personal database (previously populated by per-source smoke runs).

### Source run results

| Source | Fetched | New | Changed | Failed |
|---|---|---|---|---|
| Remote OK | 100 | 11 | 0 | 0 |
| Web3.career | — | — | — | HTTP 302 |
| Himalayas | 60 | 60 | 0 | 0 |
| Jobicy | 50 | 42 | 0 | 0 |
| Remotive | 20 | 2 | 0 | 0 |
| We Work Remotely | 93 | 5 | 0 | 0 |

Observations:

- The guided update behaved as designed: Web3.career failed in isolation, later
  sources continued, analysis still ran over successfully persisted data.
- "New" counts confirm the database previously held only partial per-source
  smoke subsets; this was the first combined six-source state.
- Idempotency held on a real rerun: unchanged postings produced no duplicate
  observations, and the intelligence phase reused 405 of 525 exact runs per
  analyzer (120 created for genuinely new postings).

### Web3.career HTTP 302 failure

The API answered every request variant (minimal, full parameter set, browser
User-Agent) with `302` redirecting to `https://web3.career/web3-jobs-api`, which
indicates server-side token rejection rather than a collector defect. The stored
100 web3_career postings are from earlier successful runs.

Action: verify/regenerate `WEB3_CAREER_API_TOKEN` from the official API page.
The collector's fail-loud behavior is correct and must not be changed to follow
the redirect.

### Dataset composition after the run

525 source postings across 6 sources:

remote_ok 111, we_work_remotely 102, himalayas 100, web3_career 100,
jobicy 92, remotive 20.

### Role classification coverage (exact-current)

Overall: 181 classified / 344 Unknown / 0 not-analyzed → **34.5% classified**.

| Source | Classified | Share |
|---|---|---|
| web3_career | 80/100 | 80.0% |
| we_work_remotely | 43/102 | 42.2% |
| himalayas | 23/100 | 23.0% |
| jobicy | 20/92 | 21.7% |
| remotive | 4/20 | 20.0% |
| remote_ok | 11/111 | 9.9% |

Findings:

- Coverage spread correlates with source domain: the role taxonomy was validated
  mostly on web3-heavy data. Non-web3 aggregator titles fall to Unknown at high
  rates.
- Remote OK's 9.9% is additionally depressed by known feed-quality issues
  (non-vacancy and boilerplate descriptions documented in ADR-011).
- This is a bounded taxonomy revision candidate, not a bug: a future Role
  Taxonomy v2 should sample Unknown titles from non-web3 sources first.

### Skill extraction coverage (exact-current)

Overall: 191 classified / 334 zero-evidence / 0 not-analyzed → **36.4% with at
least one skill mention**. Per-source shares: web3_career 69%, remotive 50%,
we_work_remotely 37%, jobicy 34%, himalayas 25%, remote_ok 16%.

### Salary availability (normalized fields)

| Source | Postings | No salary at all | Notes |
|---|---|---|---|
| remote_ok | 111 | 111 | structured salary kept raw-only by documented policy |
| web3_career | 100 | 100 | same raw-only policy |
| we_work_remotely | 102 | 102 | RSS provides no salary |
| himalayas | 100 | 62 | 38% carry structured salary |
| jobicy | 92 | 38 | ~59% carry structured salary |
| remotive | 20 | 6 | ~70% have salary text |

Salary analytics cannot be a near-term dashboard feature without first deciding
provenance policy (disclosed vs estimated) and text parsing rules.

### Stale / lifecycle signals

- We Work Remotely is the only current source with visibly old postings:
  7 postings older than 60 days, oldest from **2023-02-07**.
- All other feeds currently expose a fresh window, but postings already absent
  from feeds remain stored forever; over time the dataset accumulates rows that
  are no longer open.
- Consequence: until Job Lifecycle v1 exists, any "currently open" claim on the
  dashboard would be false. Counts must keep being described honestly as source
  postings.

---

## Sprint implications recorded from this audit

1. **Job Lifecycle v1 stays the next vertical sprint**: stale/active semantics
   are now backed by observed real data, not hypothesis.
2. **Role Taxonomy v2 candidate**: mine Unknown titles from non-web3 sources;
   target the biggest coverage gaps before adding new skills.
3. **Web3.career token renewal** is a user-side operational action.
4. **Remotive's small bounded response** (20 records despite limit) is a known
   feed limitation; monitor rather than fix.
