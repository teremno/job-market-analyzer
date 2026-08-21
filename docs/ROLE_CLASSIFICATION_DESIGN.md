# Role Classification V1

Design date: 2026-08-21

Status: implemented as a pure deterministic classifier and validated read-only against the two local smoke datasets. Role persistence is deliberately postponed.

## Contract

`extract_roles(title, description_text)` returns an immutable, deterministically ordered tuple of `RoleEvidence`. It has no database, network, source-specific, AI, or mutable-state dependency. `ROLE_TAXONOMY_VERSION = "1"` identifies the complete classification semantics.

The v1 taxonomy has 19 stable role codes:

`ai_ml`, `backend`, `blockchain_protocol`, `community`, `data`, `design`, `devops_platform`, `finance`, `frontend`, `full_stack`, `legal_compliance`, `marketing_growth`, `mobile`, `operations`, `product`, `qa`, `sales_bd`, `security`, and `support`.

There is no persisted or synthetic `other`/`unknown` role. Zero evidence is the explicit Unknown result.

## Evidence and precedence

Each evidence record contains the stable role code and name, evidence field, matched text, bounded evidence snippet, stable rule ID, and match kind.

`role_code` is the language-neutral identity. `role_name` is the current English display snapshot, not an identity or a hard-coded future UI language contract. Matcher rules are internal; the public taxonomy surface exposes only the stable ordered `ROLE_CODES` tuple and version.

Classification is title-first:

1. Direct title patterns are evaluated.
2. If the title produces any evidence, description text cannot add roles.
3. Only when the title produces zero evidence may the description be consulted.
4. Description fallback accepts an explicit role statement or role header and rejects incidental relationship language such as working with another team.

One best evidence record is emitted per role. Several roles are allowed only when the input directly supports each one, for example Community + Marketing or AI/ML + Backend + Full Stack. A general hierarchy is never inferred: Full Stack does not imply separate Frontend and Backend evidence. `Product Designer` and `Product Design Lead` are Design roles, not Product Management roles merely because `Product` appears as a modifier.

## Separate dimensions

Role, seniority, and domain remain separate dimensions. Seniority words may participate in safe title patterns but do not change role identity. Web3, crypto, blockchain, Solana, and similar terms are normally domain context; they produce Blockchain / Protocol only when the title directly names protocol, smart-contract, Solidity, on-chain, or blockchain engineering work. Generic `Web3 Developer` remains Unknown because `Web3` alone does not establish protocol work.

Data Scientist and Analytics Engineer are Data in v1. Machine Learning Engineer and Applied Scientist are AI/ML. Explicit ML Platform Engineer and Data Platform Engineer are bounded multi-label cases with DevOps / Platform. MLOps is deliberately unsupported until its desired single- or multi-label semantics are justified by real evidence.

Operations rules remain narrow. DevOps and Security Operations do not imply general Operations. Product Design maps only to Design; Product Marketing maps only to Marketing / Growth. `Support Operations` and the observed `Marketing BD Operations` retain multi-label results because their titles directly name each supported function.

The classifier does not use `source_tags`. Those tags remain available to skill analysis but are too source-dependent for this conservative role contract.

## Boundaries

- The taxonomy is intentionally conservative and English-oriented.
- Unknown means only that no v1 rule found direct evidence.
- Matching does not claim role exclusivity, confidence, seniority, employment type, or domain.
- No role rows, analysis runs, schema migration, CLI, service, or automatic collection hook are included.
- Any future semantic rule change must advance the taxonomy version once role output is persisted.

The observed coverage and manual evidence audit are recorded in [ROLE_TAXONOMY_REPORT.md](ROLE_TAXONOMY_REPORT.md).
