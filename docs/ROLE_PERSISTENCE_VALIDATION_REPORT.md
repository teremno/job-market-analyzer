# Role Persistence Validation Report

Date: 2026-08-21

## Scope

This development report validates Role Taxonomy v1 and SQLite schema v3 against disposable copies of the existing 100-posting Remote OK and 100-posting Web3.career smoke databases. No source API, token, network request, original smoke database, or production scheduler was used.

```bash
job-market-analyzer analyze-roles --database <DISPOSABLE_COPY.sqlite3> --limit 100
```

Results are posting-level validation, not globally representative market analytics. Complete cross-source canonical linking is not implemented, so combined counts are not guaranteed to represent 200 unique real-world vacancies.

## Persisted results

| Dataset | Postings | Classified | Unknown | Coverage | Multi-label | Evidence |
|---|---:|---:|---:|---:|---:|---:|
| Remote OK | 100 | 11 | 89 | 11.0% | 1 | 12 |
| Web3.career | 100 | 82 | 18 | 82.0% | 4 | 88 |
| Combined | 200 | 93 | 107 | 46.5% | 5 | 100 |

Unknown means that analysis completed and persisted an exact versioned run with zero role evidence. It does not mean failure or that the vacancy has no real role.

### Top roles by distinct posting

| Role code | Postings |
|---|---:|
| `marketing_growth` | 15 |
| `sales_bd` | 14 |
| `finance` | 10 |
| `legal_compliance` | 6 |
| `operations` | 6 |
| `product` | 6 |
| `blockchain_protocol` | 5 |
| `full_stack` | 5 |
| `security` | 5 |
| `ai_ml` | 4 |
| `backend` | 4 |
| `devops_platform` | 4 |
| `support` | 4 |
| `data` | 3 |
| `design` | 3 |
| `community` | 2 |
| `mobile` | 2 |
| `qa` | 2 |

Remote OK's top counts were `sales_bd=2`, `support=2`, and eight roles with one posting each. Web3.career's leading counts were `marketing_growth=15`, `sales_bd=12`, `finance=9`, then roles between one and five postings. Different coverage is consistent with visibly different source composition and source quality; rules were not weakened to maximize coverage.

## First and repeated runs

Both first runs considered 100 postings, created 100 role analysis runs, and failed zero postings. Remote OK created 12 evidence rows; Web3.career created 88.

Both second runs considered the same 100 postings, created zero analysis runs and zero evidence rows, reused 100 exact runs, and reproduced identical coverage, role counts, and bounded samples. Unknown runs were reused in the same way as classified runs.

The command derives every execution result from the exact `analysis_run_id` returned for the current posting input hash and active `(taxonomy_version=1, extractor_version=1)`. Historical `created_at` ordering is not used.

## Persistence and consistency audit

- All 200 current postings matched `extract_roles(title, description_text)` exactly after retrieval from their exact persisted runs: zero mismatches.
- Remote OK ended with 300 analysis runs: 100 skills v1, 100 skills v2, and 100 roles v1. It held 12 `job_roles` rows across 10 role references.
- Web3.career ended with the same 300-run version distribution. It held 88 `job_roles` rows across 18 role references.
- `PRAGMA foreign_key_check` returned zero rows for both copies after both executions.
- Deterministic digests of `canonical_jobs`, `job_postings`, `raw_jobs`, `job_skills`, `skills`, and skill-only `analysis_runs` were identical before and after role analysis.
- Invalid insert and update attempts in the real migrated schema were rejected for role evidence attached to a skill run, skill evidence attached to a role run, evidence reassignment across analyzer kinds, and analyzer-kind mutation after evidence existed.
- Persisted evidence retrieval was deterministic and contained no duplicated role code per run.

The additive initialization moved each disposable copy from schema v2 to v3. No automatic role backfill occurred during migration; role runs were created only by the explicit command.

## Multi-label audit

All five multi-label postings were manually checked against persisted evidence:

- Remote OK: `Support Operations` -> `operations`, `support`.
- Web3.career: `Pioneer Talent Program - Full Stack AI Engineer, Backend Oriented (Fully Remote)` -> `ai_ml`, `backend`, `full_stack`.
- Web3.career: `Social Media and Community Manager` -> `community`, `marketing_growth`.
- Web3.career: `Senior Security Engineer - Infrastructure` -> `devops_platform`, `security`.
- Web3.career: `Binance Accelerator Program - Marketing BD Operations` -> `marketing_growth`, `operations`, `sales_bd`.

Every role was directly supported by title evidence; no inferred parent role was added. Retrieval order was stable by role code and rule ID.

## Representative Unknown review

These are manual development-only observations and were not persisted as reason labels.

| Dataset | Title | Manual category |
|---|---|---|
| Remote OK | `Meshy` | source placeholder / non-vacancy |
| Remote OK | `Aragon AI` | source placeholder / domain-only wording |
| Remote OK | `Beehiiv` | source placeholder / non-vacancy |
| Remote OK | `Loss Prevention Specialist` | role outside taxonomy |
| Remote OK | `Typefully` | source placeholder / non-vacancy |
| Remote OK | `Staff Software Engineer` | generic / vague functional title |
| Remote OK | `Ganger` | source-data quality / unclear title |
| Remote OK | `Merchandising Execution Associate MARLBOROUGH` | role outside taxonomy |
| Remote OK | `Apify` | source placeholder / non-vacancy |
| Remote OK | `GetResponse` | source placeholder / non-vacancy |
| Web3.career | `Technical Lead - Wallets (100% remote)` | generic role plus domain wording |
| Web3.career | `Pubky - Rust Senior Engineer` | generic engineering title |
| Web3.career | `Web3 Developer - Onchain Products` | domain-only wording / intentionally conservative |
| Web3.career | `Crypto Coins & Stocks Reporter` | role outside taxonomy |
| Web3.career | `Software Engineer P2P (100% Remote, Worldwide)` | generic engineering title |
| Web3.career | `Java Engineer - Contractor` | generic engineering title |
| Web3.career | `Senior Software Engineer` | generic engineering title |
| Web3.career | `Group Legal Council` | source-data quality / possible alias typo |
| Web3.career | `Coinbase` | source placeholder / non-vacancy |
| Web3.career | `Binance Accelerator Program - CEO Office (MLO)` | vague title / role outside taxonomy |

No clear correctness defect justified changing Role Taxonomy v1. The low Remote OK coverage largely exposes placeholder, mismatched, generic, and out-of-taxonomy titles rather than a reason to accept unsafe domain inference.

## Performance and safety

A local in-memory sanity run processed 1,000 synthetic postings without quadratic behavior: pure extraction took 0.029 seconds, first persisted analysis 0.112 seconds, and exact-run reuse 0.033 seconds on the validation machine. These figures are sanity evidence, not a portable benchmark.

CLI samples are deterministic and capped at ten. They show title, company, role identity, and already-bounded extractor evidence only. The workflow does not print raw payloads or full descriptions, access environment tokens, call a network source, or modify the original smoke databases.

Original SHA-256 values before and after validation:

- `remote-ok-smoke.sqlite3`: `307504C8C4800AF37A8B93CA22931426AD0FE389D4028338904D3DE53C1767A0`
- `web3-career-smoke.sqlite3`: `FDDC128E36C8ADA1CD0D9A261226E38B0E6DDDD2E4FE9130E7E065E04E3BFF51`

## Limitations

- The datasets are two bounded local snapshots, not representative samples of the full remote market.
- Role rules are English-oriented v1. Stable `role_code` is the machine identity; English `role_name` is a separable display snapshot.
- Unknown reason categories are manual notes, not an implemented classifier.
- Current output counts source postings. Cross-source canonical linking is incomplete.
- Seniority, salary, company, geography, lifecycle, and market-demand analytics remain separate future work.
