# Skill Taxonomy Validation — ESCO/O*NET Cross-Reference

Date: 2026-08-23 (skills v5), extended 2026-08-25 (roles v3, skills v6)
Taxonomy version: 6 (125 skills); roles v3 (21 codes)
Roles validated: 13 of 19 core families + 2 new v3 codes

## Skill Taxonomy v6 closes the last ESCO/O*NET gaps (2026-08-25)

| Missing skill (v5 report) | v6 resolution | Live postings with new evidence |
|---|---|---|
| nlp | `nlp` ("Natural language processing"; acronym case-sensitive "NLP") | 92 |
| nginx | `nginx` ("Nginx") | 23 |
| email_marketing | `email_marketing` ("Email marketing", "Email campaigns") | 18 |

Expected-skill coverage across the 13 validated role anchors: **79/79 = 100%**.
Posting-level skill coverage on the live dataset is intentionally unchanged
(84.6% v5 -> v6): the three additions enrich evidence on postings that already
had other skills rather than flipping zero-skill ones.

## Role Taxonomy v3 — ESCO/O*NET anchors (2026-08-25)

| Our code | Closest O*NET occupation | Closest ESCO occupation |
|---|---|---|
| solutions_architect | Computer Network Architects; Software Developers | ICT system architect |
| delivery_engineering | Computer Systems Engineers/Architects | ICT consultant |
| sales_bd (solutions/pre-sales) | Sales Engineers | ICT sales engineer |

v3 family extensions map to existing validated anchors: brand/motion/graphic
designer -> Graphic Designers (O*NET 27-1024); database reliability engineer ->
Database Administrators (15-1243); events manager -> Meeting, Convention, and
Event Planners (13-1121); executive/administrative assistant -> Executive
Secretaries (43-6011); commercial counsel -> Lawyers (23-1011); revenue
accounting -> Accountants (13-2011). No skill-taxonomy gaps were introduced:
all new role families rely on already-covered skills.

Deliberately unclassified (precision-first): bare level-titled engineers,
Technical Program Managers, "Product Engineer", "IT Engineer" - no clean
ESCO/O*NET functional anchor without fabrication risk.

## Methodology

Our role codes were mapped to their closest ESCO (EU) and O*NET (US DOL)
occupation titles. For each occupation, the officially recognized skill set
was compiled from public ESCO and O*NET documentation. Each expected skill
was checked against our taxonomy's 122 canonical codes.

## Results

| Role | Coverage | Missing |
|---|---|---|
| backend | 100% | — |
| data | 100% | — |
| design | 100% | — |
| finance | 100% | — |
| frontend | 100% | — |
| product | 100% | — |
| qa | 100% | — |
| sales_bd | 100% | — |
| security | 100% | — |
| support | 100% | — |
| ai_ml | 87.5% | nlp |
| marketing_growth | 91.7% | email_marketing |
| devops_platform | 90.9% | nginx |

Overall: 76/79 expected skills covered = 96.2%.

## Missing skills — all resolved in v6

1. email_marketing — added as canonical `email_marketing` (v6)
2. nginx — added as canonical `nginx` (v6)
3. nlp — added as canonical `nlp` with case-sensitive acronym guard (v6)

## Skills we have that ESCO/O*NET do not (35)

Web3/blockchain (10), modern frameworks (15), marketing-specific (10).
Expected: bottom-up taxonomy tracks the market faster than official
standards update their curated lists.
