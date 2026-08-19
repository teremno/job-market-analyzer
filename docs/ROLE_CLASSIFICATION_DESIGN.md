# Role Classification Design Proposal

Design date: 2026-08-19

Status: proposal for human review; no role code, schema, or persisted role output exists yet.

This proposal uses titles observed in the local 100-posting Remote OK and 100-posting Web3.career smoke datasets. Those samples are small and not market-representative. The first implementation should be deterministic, multi-label, evidence-bearing, and conservative. `Unknown` is a valid result.

## Dimensions that must remain separate

Role, seniority, and domain answer different questions and must not be collapsed into one label:

- **role** — the work performed, such as Data, Security, Product, or Sales/BD;
- **seniority** — Junior, Mid, Senior, Staff, Principal, Lead, Head, VP, C-level, or Unknown;
- **domain** — Web3, blockchain, Solana, wallets, compliance, retail, and similar context.

The original source title remains unchanged on `JobPosting`. Classification is derived output only.

## Proposed minimal v1 role categories

| Code | Label | Representative persisted local titles |
|---|---|---|
| `backend` | Backend | `Backend Engineer`, `Remote Founding Engineer - Backend` |
| `full_stack` | Full Stack | `Full Stack Engineer`, `Full Stack Engineer - KYC Tech (fully remote!)` |
| `mobile` | Mobile | `Software Engineer III Mobile`, `Senior/Staff React Native Engineer` |
| `devops_platform` | DevOps / Platform | `Infrastructure / Systems Operations Engineer`, `Senior Software Engineer, Developer Platform` |
| `data` | Data | `Senior Data Engineer`, `Blockchain Data Engineer`, `Software Engineer - Data` |
| `ai_ml` | AI / ML | `Artificial Intelligence Specialist`, `Founding AI Engineer - Internal Copilot Platform` |
| `security` | Security | `Public Facing Security Researcher`, `Senior IT Security Engineer`, `Principal Security Engineer (Solana)` |
| `qa` | QA | `QA Tester Entry Level`, `Quality Assurance Engineer` |
| `blockchain_protocol` | Blockchain / Protocol | `Solidity Protocol Engineer`, `Senior Blockchain Engineer` |
| `product` | Product | `Product Manager`, `Founding Product Manager`, `Product Lead (Blockchain)` |
| `design` | Design | `Product Design Lead`, `Product Designer` |
| `marketing_comms` | Marketing / Growth / Communications | `Growth Marketing Manager`, `PR & Communications Associate - Contractor` |
| `sales_bd` | Sales / Business Development | `P2P BD Assistant`, `Sales Manager`, `Web3 BD` |
| `community` | Community | `Community Manager`, `Social Media and Community Manager` |
| `support_trust_safety` | Support / Trust & Safety | `Customer support agent`, `Team Lead, Trust & Safety Ops (Bangalore)` |
| `finance` | Finance | `VP of Finance` |
| `legal_compliance` | Legal / Compliance | `Senior Legal Counsel`, `Head of Compliance` |
| `operations` | Operations | `Chief Operating Officer`, `Director of Operations`, `Support Operations` |
| `other_unknown` | Other / Unknown | `Title TBD`, `Custom Role`, `Current Openings`, `Available Position (Company name withheld)` |

No clear standalone Frontend title appeared in this 200-posting sample. A future `frontend` category is likely useful, but it should not be activated in deterministic v1 until actual supporting examples and false-positive fixtures are reviewed. Full Stack does not automatically imply a separate Frontend label.

## Multi-label behavior

A posting may have more than one role when the title directly supports each label:

- `Pioneer Talent Program - Full Stack AI Engineer, Backend Oriented (Fully Remote)` → Full Stack + Backend + AI/ML;
- `Full-Stack Software Engineer - Compliance` → Full Stack + Legal/Compliance only if the description confirms compliance work rather than a team name;
- `Product Design Lead` → Product + Design;
- `Binance Accelerator Program - Marketing BD Operations` → Marketing/Communications + Sales/BD + Operations;
- `Blockchain Data Engineer` → Data, with Blockchain as a domain; add Blockchain/Protocol only when evidence confirms protocol-level work.

No hierarchy should infer unmentioned parent roles. Backend must not automatically imply Full Stack, and Product Design must not automatically imply Frontend.

## Seniority separation

Seniority should be extracted by a separate versioned analyzer from explicit title terms such as `Junior`, `Mid`, `Senior`, `Staff`, `Principal`, `Lead`, `Head`, `VP`, `Chief`, and `Founding`. Role rules must ignore those tokens when choosing role labels.

Examples:

- `Senior Data Engineer` → role Data; seniority Senior;
- `Principal Security Engineer (Solana)` → role Security; seniority Principal; domain Solana;
- `Chief Operating Officer` → role Operations; seniority C-level;
- `Infrastructure / Systems Operations Engineer (Junior to Mid)` → role DevOps/Platform, possibly Operations; seniority range Junior-to-Mid.

Ambiguous modifiers such as `Lead` may describe responsibility rather than a standardized employment level. The analyzer should preserve explicit evidence instead of forcing a total ordering.

## Web3 domain versus role

Web3 terms usually modify a role rather than replace it:

- `Web3 BD` → Sales/BD + Web3 domain;
- `Product Lead (Blockchain)` → Product + Blockchain domain;
- `Principal Security Engineer (Solana)` → Security + Solana domain;
- `Blockchain Data Engineer` → Data + Blockchain domain;
- `Solidity Protocol Engineer` → Blockchain/Protocol because the title directly names protocol engineering.

Bare `Web3`, `crypto`, `blockchain`, `Bitcoin`, or `Solana` must not turn Product, Marketing, Sales, Legal, or Community work into Blockchain/Protocol engineering.

## Ambiguous and low-quality titles

Title-only classification should return Unknown for `404`, `Current Openings`, `Title TBD`, `Custom Role`, `Member of Technical Staff Engineering`, and `Available Position (Company name withheld)` unless bounded description evidence resolves a role safely.

`BD` is also ambiguous in isolation. It may become Sales/BD only when the description explicitly expands it to business development. `Support Operations` may support both Support and Operations, while `Infrastructure / Systems Operations Engineer` needs technical context to distinguish Platform work from general Operations.

## Deterministic v1 strategy

1. Normalize only comparison whitespace and case; preserve the source title unchanged.
2. Match stable phrase rules with token boundaries, longest-safe alias first.
3. Use title evidence first. Consult a bounded description window only for explicitly ambiguous titles or abbreviations.
4. Emit zero, one, or several role labels with `evidence_field`, short evidence text, stable `rule_id`, and match kind.
5. Keep role, seniority, and domain outputs separate and independently versioned.
6. Hash only fields actually consumed by that analyzer.
7. Persist an explicit successful zero-label run so Unknown is reproducible and idempotent.
8. Advance the semantics version for any rule, boundary, precedence, or evidence change.

AI is not required for v1. A later AI-assisted comparison may be evaluated separately, but it must not overwrite deterministic evidence or authoritative posting fields.

## False-positive risks

- `Product` may refer to a product area in an engineering title rather than Product Management.
- `Operations` appears in infrastructure, support, marketing, and executive roles.
- `Security` may describe a product property instead of a security role.
- `Data` may occur in generic responsibilities without defining the job family.
- `Lead` can be seniority, responsibility, or part of a nonstandard title.
- `BD`, `QA`, `AI`, and `ML` need explicit abbreviation boundaries and context.
- Blockchain-domain words can overwhelm the actual functional role.
- Remote OK placeholder, non-vacancy, repeated-description, encoding, and language problems can make description fallback unreliable.

Each accepted ambiguous rule needs both positive and adversarial regression examples drawn from real persisted titles.

## Proposed future persistence shape

Reuse the existing versioned `analysis_runs` identity with a future role-specific repository boundary and `analyzer_kind = roles`. Add a separate derived `job_roles` evidence table only when implementation is approved. It should snapshot at least:

- stable `role_code` and display name;
- evidence field and bounded evidence text;
- stable rule ID and match kind;
- direct classification semantics, not confidence invented by the source model.

Seniority and domain should use their own derived evidence records or analysis kinds. None of these outputs belongs in `RawJob`, normalized source fields, or `CanonicalJob`. Historical labels must be snapshotted so later reference-name changes cannot rewrite old results.

## Explicit non-goals

- no role implementation, schema migration, or tests in this checkpoint;
- no single forced role for every posting;
- no combined role-seniority-domain mega-label;
- no company normalization or identity resolution;
- no cross-source canonical linking;
- no market demand ranking or employment recommendation;
- no AI, LLM, embeddings, confidence fabrication, API, bot, scheduler, or web interface.
