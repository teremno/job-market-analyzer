# Self-Reflection Report - Full Day Sprint Analysis

Date: 2026-08-24 (covering 2026-08-22-23)
Commits analyzed: ~25
Tests: 838 to 858 (net +20 despite 3 schema migrations and 2 source additions)

---

## 1. Bug Pattern Analysis

| Pattern | Count | Examples | Root Cause |
|---|---|---|---|
| P1: Environment/config drift | 3 | 0.0.0.0 bind blocker, web Dockerfile context, Caddy crash-loop from empty DOMAIN | Deploy path exercised for the first time AT deploy time |
| P2: Precision bugs on real data | 4 | Clear filters, salary median bias, collector metadata, taxonomy FPs | Manual testing only; real data exposed what fixtures missed |
| P3: Workspace leakage | 3 | .opencode file, debug script, stray log committed | No artifact gate before commit |
| P4: Knowledge gap | 3 | Marketing blind spot, missing LICENSE, Ashby compensation reversal | Team could not enumerate non-tech skill language |
| P5: External dependency drift | 1 | Web3.career token expired | No token-expiry monitoring |
| P6: Guard-after-persist churn | 2 | v4 to v5 same-day version bump | Aliases shipped for recall, guards added reactively |
| P7: Untested scale assumptions | 1 | Dashboard queries collapsed at 7,413 rows | Never re-measured after dataset grew 14x |
| P8: Cross-platform encoding | 1 | Mojibake in PROJECT_HANDOFF and GRANTS_NOTES | gitattributes added late |

## 2. Process Lessons

### What worked
- Audit-driven sprint selection (morning audit produced best decisions)
- Registry-driven extensibility (10 platforms in 1 day, zero orchestration changes)
- Versioned analysis runs (4 taxonomy revisions, zero data loss)
- Tri-agent review (caught real shipped bugs both times)
- One vertical sprint = one coherent commit

### What did not
- Decision churn on unverified assumptions (Ashby comp ADR-024 to ADR-026 same day)
- Same-day version bumps (v4 to v5 for guard fixes)
- Cold deployment at night with sed handoff instructions
- Docs sync always a catch-up commit, never in-sprint

## 3. Architecture Lessons

### Proven correct
- (input_hash, version) exact-current resolution survived 4 taxonomy revisions
- Additive-only schema migrations with triggers: 5 analyzers, no conflicts
- Read-only analytics boundary: dashboard shipped as pure consumer
- Posting-level honesty discipline: every doc says "source postings"

### Caused friction
- Single coupled taxonomy==extractor version: any alias tweak bumps globally
- Python SHA UDF full scans: needed emergency optimization at 7k rows
- No canonical deduplication: public counts inflated by cross-source duplicates
- Production serves frozen snapshot: no update worker, freshness decaying

## 4. Knowledge Gaps

1. Git ignore negation patterns (.env* globbing .env.production.example)
2. Windows to Linux encoding/EOL (mojibake, late gitattributes)
3. ATS API capability surface (Ashby includeCompensation existed all along)
4. Non-tech domain vocabularies (marketing/sales/ops skill language)
5. Open-source release prerequisites (LICENSE/CONTRIBUTING/SECURITY)

## 5. Top 5 Recommendations

### R1. Make deployment rehearseable
Add to CI: compose config validation, env-var existence check, deploy smoke script. Eliminates the entire P1 bug class.

### R2. Gate taxonomy revisions with gold-set FP/FN suite
Each ambiguous alias gets positive/negative/guard cases. No version bump ships unless the suite passes.

### R3. Production update worker + source health visibility
Systemd timer running update against server DB. Expose last successful update per source on the Sources page.

### R4. Fix documentation integrity mechanically
UTF-8 conformance check in CI. Pre-commit hook rejecting stray files.

### R5. Security sprint before any more surface growth
Rate limiting, auth scoping, salary presentation caveat, canonical dedup v1.

---

## Summary

The architecture proved it can absorb breakneck velocity. But velocity repeatedly
outran verification: of external APIs, of environments, of scale, and of output
hygiene. Every bug class today was a verification gap, not a design flaw.
