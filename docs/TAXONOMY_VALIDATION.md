# Skill Taxonomy Validation — ESCO/O*NET Cross-Reference

Date: 2026-08-23
Taxonomy version: 5 (122 skills)
Roles validated: 13 of 19

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

## Missing skills (all scheduled for v6)

1. email_marketing — identified by mining, deferred from v3
2. nginx — tool, covered by linux + devops_platform role
3. nlp — covered by machine_learning + llm + prompt_engineering

## Skills we have that ESCO/O*NET do not (35)

Web3/blockchain (10), modern frameworks (15), marketing-specific (10).
Expected: bottom-up taxonomy tracks the market faster than official
standards update their curated lists.
