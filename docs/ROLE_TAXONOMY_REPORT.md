# Role Taxonomy V1 Validation Report

Validation date: 2026-08-21

This report records a read-only validation of the deterministic classifier against the current local `remote-ok-smoke.sqlite3` and `web3-career-smoke.sqlite3` databases. Each contains 100 current postings. The samples are small, source-skewed, and not market-representative.

## Taxonomy and evidence contract

The validated semantics are `ROLE_TAXONOMY_VERSION = "1"`. The stable role codes are:

`ai_ml`, `backend`, `blockchain_protocol`, `community`, `data`, `design`, `devops_platform`, `finance`, `frontend`, `full_stack`, `legal_compliance`, `marketing_growth`, `mobile`, `operations`, `product`, `qa`, `sales_bd`, `security`, and `support`.

Classification is title-first. Description fallback runs only for a title with zero evidence and accepts only an explicit role statement or header. Direct compound titles may produce several labels, but no hierarchy, seniority, domain, or skill relationship is inferred. Unknown is represented by zero evidence. Evidence preserves the matched source text and a bounded Unicode-safe snippet; it does not claim confidence, exclusivity, or that a role is required.

The stable identity is the language-neutral `role_code`; the English `role_name` is a current display snapshot. Regex rules and rule helper structures are not exported from the package-level public API.

## Results

| Dataset | Postings | Classified | Unknown | Multi-label | Evidence records | Title evidence | Description evidence |
|---|---:|---:|---:|---:|---:|---:|---:|
| Remote OK | 100 | 11 | 89 | 1 | 12 | 12 | 0 |
| Web3.career | 100 | 82 | 18 | 4 | 88 | 87 | 1 |
| Combined | 200 | 93 | 107 | 5 | 100 | 99 | 1 |

Combined posting coverage is 46.5%. This is classifier coverage on these two snapshots, not a demand estimate.

## Combined evidence counts

| Role | Evidence records |
|---|---:|
| Marketing / Growth | 15 |
| Sales / Business Development | 14 |
| Finance | 10 |
| Legal / Compliance | 6 |
| Product | 6 |
| Operations | 6 |
| Blockchain / Protocol | 5 |
| Full Stack | 5 |
| Security | 5 |
| AI / ML | 4 |
| Backend | 4 |
| DevOps / Platform | 4 |
| Support / Trust & Safety | 4 |
| Data | 3 |
| Design | 3 |
| Community | 2 |
| Mobile | 2 |
| QA | 2 |
| Frontend | 0 |

These are evidence counts, not deduplicated CanonicalJob market analytics.

## Manual audit

At least thirty classified postings were reviewed across both sources, including all Blockchain / Protocol results and all unusual AI/ML, Data, Security, business, and compound titles. Twenty Remote OK Unknown postings and all eighteen Web3.career Unknown postings were reviewed. All five multi-label results were also reviewed:

- `Support Operations` -> Operations + Support;
- `Pioneer Talent Program - Full Stack AI Engineer, Backend Oriented` -> AI/ML + Backend + Full Stack;
- `Social Media and Community Manager` -> Community + Marketing / Growth;
- `Security Engineer - Infrastructure` -> DevOps / Platform + Security;
- `Marketing BD Operations` -> Marketing / Growth + Operations + Sales / Business Development.

The only description fallback was an intentionally vague Web3.career title whose description explicitly said the employer was looking for a marketer. No reviewed result showed an obvious matcher false positive. One Remote OK `Support Operations` record had an apparently unrelated manufacturing description; title-first behavior correctly preserved direct title evidence and exposed this as source-data quality rather than expanding from the bad description.

Hardening removed three over-broad interpretations: `Product Design Lead` is Design only, `Group Legal Council` remains Unknown rather than treating `council` as `counsel`, and generic `Web3 Developer` remains Unknown rather than treating a domain word as protocol-engineering evidence. Safe direct aliases and boundaries were added for Backend / Platform compounds, parenthesized Backend, Dev Ops, Security Operations, Finance Manager, Quant Researcher, AML Analyst, Sales Engineer, and Unicode dash separators.

## Known limitations

- Remote OK contains many placeholder, non-vacancy, non-English, malformed, or apparently mismatched records, which explains much of its high Unknown rate.
- Several generic engineering titles intentionally remain Unknown because they do not directly identify a role family.
- The rules are primarily English-language and do not transliterate or translate titles.
- Non-English text therefore normally remains Unknown unless it contains a directly supported English role phrase. Future language-specific rules can retain the same stable machine codes and version their semantics without changing the domain contract.
- `frontend` had no accepted evidence in this snapshot; the category remains because it has explicit regression fixtures and is a useful stable role family.
- Cross-source CanonicalJob linking is incomplete, so the report does not claim cross-source deduplicated demand.
- No derived role output was written to either database during validation.
