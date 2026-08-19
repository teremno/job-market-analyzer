# Skill Taxonomy Local Validation Report

Validation date: 2026-08-19

This is a development and taxonomy-validation report. It is not product marketing, final market analytics, or a claim about the global remote-job market. Counts are posting-level because complete cross-source canonical linking is not implemented.

## Scope and method

The active deterministic analyzer was run locally against two existing SQLite smoke databases:

- 100 Remote OK `JobPosting` rows;
- 100 Web3.career `JobPosting` rows.

No vacancy collection, network request, external API, token, AI, or LLM was used. The command read current durable postings, persisted versioned evidence, and was repeated unchanged to verify idempotency.

The final hardened v2 semantics were recomputed on disposable SQLite copies after adversarial review tightened bare `Bash` and added safe `Kafka Streams` and `Snowflake warehouse` aliases. Only copied v2 derived rows were cleared; v1 evidence and all source/domain rows were retained. The two original ignored smoke databases were not deleted, reset, or rewritten.

Both databases predated normalized `source_tags` and began at schema version `0`. The tested additive migration advanced them to schema version `2` and assigned the documented empty source-tag tuple to legacy postings. Therefore this dataset cannot validate real source-tag recognition; all observed evidence came from title or description.

## Dataset and posting-level coverage

| Dataset | Postings | Version | With at least one skill | Zero skill | Coverage | Evidence rows | Unique observed skill codes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Remote OK | 100 | v1 | 15 | 85 | 15.0% | 37 | 20 |
| Remote OK | 100 | v2 | 16 | 84 | 16.0% | 41 | 23 |
| Web3.career | 100 | v1 | 62 | 38 | 62.0% | 175 | 30 |
| Web3.career | 100 | v2 | 67 | 33 | 67.0% | 225 | 43 |
| Combined | 200 | v1 | 77 | 123 | 38.5% | 212 | 33 |
| Combined | 200 | v2 | 83 | 117 | 41.5% | 266 | 46 |

The combined v2 delta is six postings, 3.0 percentage points, 54 evidence rows, and 13 newly observed canonical codes. A higher coverage percentage alone is not proof of better quality; the v2 rules were accepted only after direct evidence and false-positive review.

## Top skills by distinct posting count

Repeated evidence fields within one posting count once in these tables.

### Remote OK v1

| Skill code | Display name | Postings |
|---|---|---:|
| `git` | Git | 8 |
| `go` | Go | 3 |
| `javascript` | JavaScript | 3 |
| `aws` | AWS | 2 |
| `cicd` | CI/CD | 2 |
| `gcp` | Google Cloud | 2 |
| `kubernetes` | Kubernetes | 2 |
| `python` | Python | 2 |
| `terraform` | Terraform | 2 |
| `dotnet` | .NET | 1 |

### Remote OK v2

| Skill code | Display name | Postings |
|---|---|---:|
| `git` | Git | 8 |
| `go` | Go | 3 |
| `javascript` | JavaScript | 3 |
| `aws` | AWS | 2 |
| `cicd` | CI/CD | 2 |
| `gcp` | Google Cloud | 2 |
| `kubernetes` | Kubernetes | 2 |
| `python` | Python | 2 |
| `snowflake` | Snowflake | 2 |
| `terraform` | Terraform | 2 |

### Web3.career v1

| Skill code | Display name | Postings |
|---|---|---:|
| `defi` | DeFi | 35 |
| `aws` | AWS | 16 |
| `ethereum` | Ethereum | 13 |
| `solidity` | Solidity | 11 |
| `typescript` | TypeScript | 11 |
| `python` | Python | 9 |
| `javascript` | JavaScript | 7 |
| `kubernetes` | Kubernetes | 7 |
| `nodejs` | Node.js | 7 |
| `git` | Git | 5 |

### Web3.career v2

| Skill code | Display name | Postings |
|---|---|---:|
| `defi` | DeFi | 35 |
| `aws` | AWS | 16 |
| `ethereum` | Ethereum | 13 |
| `evm` | EVM | 12 |
| `solidity` | Solidity | 11 |
| `typescript` | TypeScript | 11 |
| `python` | Python | 9 |
| `javascript` | JavaScript | 7 |
| `kubernetes` | Kubernetes | 7 |
| `nodejs` | Node.js | 7 |

### Combined v1

| Skill code | Display name | Postings |
|---|---|---:|
| `defi` | DeFi | 35 |
| `aws` | AWS | 18 |
| `ethereum` | Ethereum | 14 |
| `git` | Git | 13 |
| `typescript` | TypeScript | 12 |
| `python` | Python | 11 |
| `solidity` | Solidity | 11 |
| `javascript` | JavaScript | 10 |
| `kubernetes` | Kubernetes | 9 |
| `go` | Go | 8 |

### Combined v2

| Skill code | Display name | Postings |
|---|---|---:|
| `defi` | DeFi | 35 |
| `aws` | AWS | 18 |
| `ethereum` | Ethereum | 14 |
| `git` | Git | 13 |
| `evm` | EVM | 12 |
| `typescript` | TypeScript | 12 |
| `python` | Python | 11 |
| `solidity` | Solidity | 11 |
| `javascript` | JavaScript | 10 |
| `kubernetes` | Kubernetes | 9 |

These are mention counts, not proof that a technology is required, preferred, or central to the vacancy.

## Evidence-field distribution

| Dataset | Version | Title | Description | Source tag | Total |
|---|---:|---:|---:|---:|---:|
| Remote OK | v1 | 1 | 36 | 0 | 37 |
| Remote OK | v2 | 1 | 40 | 0 | 41 |
| Web3.career | v1 | 6 | 169 | 0 | 175 |
| Web3.career | v2 | 8 | 217 | 0 | 225 |
| Combined | v1 | 7 | 205 | 0 | 212 |
| Combined | v2 | 9 | 257 | 0 | 266 |

The lack of tag evidence is a legacy-dataset limitation, not evidence that current collectors fail to persist tags.

## Zero-skill review

Twenty representative v2 zero-skill rows were inspected manually without copying full descriptions. The review labels are qualitative validation notes, not persisted product data:

- **A** — likely nontechnical;
- **B** — technical but taxonomy gap;
- **C** — insufficient or vague input;
- **D** — non-English or damaged encoding;
- **E** — source/data-quality problem;
- **F** — intentionally conservative no-match.

| Source | Actual title | Class | Review finding |
|---|---|:---:|---|
| Remote OK | `Loss Prevention Specialist` | A/E | Nontechnical role with repeated generic retail prose |
| Remote OK | `Ganger` | A | Municipal field-work role |
| Remote OK | `Artificial Intelligence Specialist` | C/F | Vague AI wording without a concrete accepted technology |
| Remote OK | `Seeking a job` | E | Candidate advertisement, not a vacancy |
| Remote OK | `Project leaders` | C | Generic role description without concrete technology |
| Remote OK | `Customer Service Representative` | A | Nontechnical customer-service role |
| Remote OK | `Software Engineer III Mobile` | D | Portuguese and visibly damaged encoding in the persisted text |
| Remote OK | `Title TBD` | C/E | Placeholder vacancy |
| Remote OK | `Test Job Title` | E | Test data rather than a credible vacancy |
| Remote OK | `ANALYST L3` | B | Clear IBM BAW omission, but only one observed vacancy |
| Web3.career | `Chief Operating Officer` | A | Executive operations role |
| Web3.career | `Crypto Coins & Stocks Reporter (Remote - New York)` | A | Editorial role |
| Web3.career | `PR & Communications Associate - Contractor` | A | Communications role |
| Web3.career | `Public Facing Security Researcher` | B | Technical security/formal-verification concepts without accepted tool aliases |
| Web3.career | `Web3 BD` | A/F | Business-development role; broad Web3 domain is deliberately not a skill |
| Web3.career | `Available Position (Company name withheld)` | C | Vague title insufficient for deterministic classification |
| Web3.career | `Community Manager` | A | Community role |
| Web3.career | `Team Lead, Trust & Safety Ops (Bangalore)` | A | Operations/compliance role |
| Web3.career | `Senior Software Engineer` at Base | E | Persisted description is only an application-verification sentence |
| Web3.career | `Product Lead (Blockchain)` | F | Product role; broad blockchain domain is intentionally not a concrete skill |

Remote OK's low coverage is dominated by dataset composition and quality, not only taxonomy omissions. Adding broad aliases to force higher coverage would hide that fact.

## Source tags and unrecognized tags

All 200 legacy postings have `source_tags_json = []` after the documented migration. Consequently:

- no factual unrecognized-source-tag frequency can be reported for this dataset;
- raw payloads were not reinterpreted as current normalized postings;
- taxonomy v2 was based on durable title/description evidence only.

A future collection using current normalizers is required before source-tag coverage can be evaluated.

## Data-driven v2 changes

V2 adds 13 canonical codes. Counts below are distinct v2 postings across both databases.

| Code | Display name | Postings | Acceptance evidence |
|---|---|---:|---|
| `evm` | EVM | 12 | Web3 stacks, literacy, indexer, and protocol contexts |
| `figma` | Figma | 7 | Product-design use, Figma AI, fluency, and explicit collaboration tooling |
| `solana` | Solana | 5 | Engineer title, explicit experience/familiarity, wallet/indexer contexts |
| `bash` | Bash | 4 | Shell scripting and security automation contexts |
| `css` | CSS | 3 | Explicit web stack and implementation mentions |
| `html` | HTML | 3 | Explicit web stack and implementation mentions |
| `kafka` | Apache Kafka | 3 | Streaming platform, middleware, and tech-stack contexts |
| `linux` | Linux | 3 | Infrastructure administration and QA platform coverage |
| `prometheus` | Prometheus | 3 | Monitoring, observability, and middleware contexts |
| `react_native` | React Native | 3 | Mobile engineering title/stack contexts |
| `snowflake` | Snowflake | 3 | Data engineering, warehouse, dbt, and tech-stack contexts |
| `cosmos` | Cosmos | 2 | Explicit blockchain-node experience |
| `grafana` | Grafana | 2 | Monitoring and observability tooling |

V2 does not add broad `Blockchain`, `Web3`, or `Bitcoin` codes. They appeared 63, 37, and 15 times respectively, but many occurrences described industry, employer, finance, marketing, product, or editorial context rather than a concrete skill.

## False-positive protections

- Bare `Bash` requires shell, scripting, automation, terminal, CLI, DevOps, or SRE context; sentence-initial prose such as “Bash the old box” is rejected. `Bash shell` is safe direct evidence.
- `Kafka` rejects `Franz Kafka` and requires streaming, broker, middleware, or technical-stack context; `Apache Kafka` is safe direct evidence.
- `Prometheus` requires monitoring, observability, metrics, Grafana, middleware, or related infrastructure context.
- `Snowflake` requires data engineering, warehouse, analytics, SQL/dbt, BigQuery, Databricks, Airflow, cloud, or tech-stack context.
- `Cosmos` requires blockchain, Web3, node, chain, or SDK context.
- Bare `Figma` requires explicit design, fluency/use, Figma AI, or collaboration-tooling context. Boilerplate such as “Trusted by Meta, Figma, Autodesk” is rejected.
- Bare `Solana` requires engineering, indexer, SDK, development, explicit experience/familiarity, or wallet context. Price pages and Solana Foundation employer boilerplate are rejected.
- `HTML`, `CSS`, and `EVM` use case/boundary-conscious direct aliases. `Kafka Streams` and `Snowflake warehouse` are safe compound aliases.
- `React Native` and `Ethereum Virtual Machine` suppress shorter contained aliases rather than inferring React or Ethereum automatically.

Adversarial tests also cover mythology, astronomy, winter decorations, literary names, ordinary verbs, partial phrases, and generic company/platform prose.

The manual false-positive pass inspected all 50 v2-addition evidence rows across 28 distinct actual postings, exceeding the requested 20-posting sample. The accepted evidence included infrastructure Bash, Cosmos nodes, web-stack HTML/CSS, EVM engineering, explicit Figma tooling, monitoring Grafana/Prometheus, Kafka data stacks, Linux administration, React Native mobile work, Snowflake data stacks, and technical Solana experience. No obvious matcher false positive remained. One `React Native` mention on a Remote OK `Senior Data Engineer` row came from a visibly mismatched recruiter description; that is source-data mismatch, not a fabricated match against the persisted text.

## Candidate omissions after v2

### High-confidence technical candidates for a later version

- `BigQuery`: 3 explicit data-stack mentions.
- `Sass`: 2 explicit web-stack mentions.
- `Ruby on Rails`: 2 genuine tech-stack mentions, but four additional “payment rails” occurrences require a contextual guard.
- `Shell scripting`: 2 explicit mentions already accompanied by Bash evidence; a separate canonical code is not yet justified.
- `Airflow`, `gRPC`, and `Vyper`: one clear technical mention each; more data is desirable before expansion.
- `IBM BAW`: one explicit mandatory-skill vacancy; too little evidence for this bounded revision.

### Possible skill or domain; needs review

- `Blockchain`, `Web3`, and `Bitcoin`: frequent but often industry/product context.
- `Swift`: four strings, but three refer to the SWIFT organization and only one is a programming-language list.
- `Oracle`: four strings, all related to blockchain oracle concepts rather than Oracle Database.
- AI/ML, formal verification, security research, and QA role language may need future role/capability models rather than direct skill aliases.

### Not a skill or unsafe general token

- bare `Move`: 22 candidate-string occurrences were dominated by the ordinary verb; a future Move-language rule would need strong programming context.
- bare `rails`: four of six occurrences meant financial/payment infrastructure, not Ruby on Rails.
- generic `blockchain`, `crypto`, `remote`, `senior`, `engineering`, and job-category labels must not be promoted automatically.

## Historical runs, idempotency, and integrity

After v2 validation each database contains 200 analysis runs: 100 v1 and 100 v2. Final-v2 copies created 100 replacement v2 runs on the first pass and reused all 100 on the second pass.

The original Remote OK v2 evidence digest matches final v2 exactly. The original ignored Web3.career database retains the pre-hardening uncommitted v2 rows because the source database was deliberately not reset: its 225 evidence rows differ from final v2 in exactly four fields, where technical `Bash` evidence changes from `exact_alias` to `contextual`. Skill codes, posting coverage, evidence counts, v1 evidence, and all source/domain rows are otherwise unchanged. Final reported semantics come from the disposable copy.

| Database | V1 evidence | V2 evidence | Second v2 run: new runs | Second v2 run: new evidence | FK violations |
|---|---:|---:|---:|---:|---:|
| Remote OK | 37 | 41 | 0 | 0 | 0 |
| Web3.career | 175 | 225 | 0 | 0 | 0 |

V1 evidence counts remained unchanged after final-v2 recomputation. Current source-table row counts remained 100 canonical jobs, 100 postings, and 100 raw observations in each database. Full-row SHA-256 snapshots for `canonical_jobs`, `job_postings`, and `raw_jobs` matched the pre-hardening baseline in both copies. `PRAGMA foreign_key_check` returned no rows, and both databases report schema version `2`.

The first Remote OK v1 execution exposed a CP1251 console-output failure after all 100 runs had committed. A regression now configures CLI streams to replace characters unavailable in the active Windows encoding. Post-fix Remote OK runs completed with exit code 0 and reused all 100 v1 runs; Web3.career's first v1 run created 100 runs and its second reused all 100.

## Known limitations

- Only 200 locally persisted postings were inspected.
- These datasets are not a random or representative market sample.
- Remote OK contains non-vacancies, placeholders, malformed encoding, and apparently mismatched or repeated boilerplate descriptions.
- Exact evidence can be true for the persisted text but irrelevant to the vacancy when source data itself is mismatched; repeated Git evidence in unrelated AI Supermarket rows demonstrates this.
- Evidence means `mentioned`, not required or preferred.
- Source-tag coverage is unavailable in these legacy databases.
- Counts are posting-level, not fully cross-source-deduplicated canonical demand.
- English-oriented deterministic rules miss non-English or damaged text.

## Recommended next role-classification checkpoint

Local titles support a small multi-label role taxonomy, not a single forced label:

- engineering: Backend, Frontend, Full Stack, Mobile, DevOps/Platform, Data, AI/ML, Security, QA, Blockchain/Protocol;
- product and design: Product, Product Design;
- go-to-market: Marketing/Growth/Communications, Sales/Business Development, Community;
- service and governance: Support/Trust & Safety, Finance, Legal/Compliance, Operations;
- `Other` and `Unknown` for non-vacancies, vague titles, and unsupported roles.

Seniority must be a separate derived dimension. Web3 should normally be a domain modifier rather than forcing every role into a Web3 role. Multi-label examples include `Full-Stack Software Engineer - Compliance`, `Technical Lead - Wallets`, and `Blockchain Data Engineer`. Ambiguous titles such as `Member of Technical Staff`, `Available Position`, `BD`, and `Custom Role` must remain unknown unless description evidence resolves them.

The next checkpoint should define a versioned, evidence-bearing role-analysis contract and test it against local titles. It should not add role fields to authoritative `JobPosting`, infer company identity, or combine role extraction with seniority.
