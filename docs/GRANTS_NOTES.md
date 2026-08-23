# Grants & Hackathons Notes

Verified snapshot of external funding opportunities relevant to this project.
Re-verify before acting — terms change.

---

## Sentient Foundation — Open Source AGI Grant Programme

Verified: 2026-08-23 against https://sentient.foundation/grants and press coverage.

| Item | Fact |
|---|---|
| Fund size | $42M committed (announced June 2026) |
| Deadline | None — applications reviewed on a rolling basis |
| Tracks | (1) Non-dilutive grants for open-source maintainers / independent developers / public goods; (2) founder-friendly investments for startups |
| Ownership | Recipients keep IP; no equity, no lockups on the grant track |
| Openness bar | At least one essential element openly available; full stack opening is NOT required |
| Evaluation | Technical merit, ecosystem impact, openness, long-term potential; named technical panel; deliberate reach into multilingual and underserved markets |
| Extras | Distribution help, compute credits, engineering support, builder community |
| Apply | Typeform linked from https://sentient.foundation/grants |

### Fit assessment for Job Market Analyzer

Strong alignment:

- Multilingual reach is an explicit foundation priority; our planned
  multilingual explanation layer (user-language explanations over English
  market evidence) matches their stated product examples.
- Self-hosted/local mode with SQLite maps to their "Accessible" and
  "Private by default" principles.
- Public-good positioning: free evidence-based career guidance without paid
  consultants; open source with honest licensing.

Gap to close before applying:

- An AI explanation/recommendation layer grounded in our deterministic
  evidence (the foundation funds AI products; pure deterministic analytics
  alone is a weaker story). This is exactly the handoff §63 demo milestone:
  market data + skill gap + recommendations + AI explanation + multilingual
  output as a real capability.

### Recommended sequence

1. Deploy the public read-only alpha (working proof).
2. Add the multilingual AI-explanation layer over structured evidence.
3. Apply with a live demo, repository, and the positioning drafted in
   PROJECT_HANDOFF §62 (never pitch "a job scraper").


---

## Application-readiness plan (deep research pass, 2026-08-23)

Research verified against: sentient.foundation/grants, /product-requests
(all 27 RFPs catalogued), the live Typeform schema (IRj7WaKH), official
announcement, Forbes/TNW coverage, website ToS.

### Key verified facts

- Amount menu: $10k / $25k / $50k / >$50k (grant track).
- Form long-text screens: problem+why-now; who-it-helps+where; one-line ≤80
  chars; team; **"what's open about it"** (core screen); demo links REQUIRED;
  document upload REQUIRED.
- Screening: "conviction, real building, genuine value, not polish".
- No career-guidance RFP exists; general banner applies ("people the market
  forgot"). Closest RFP hooks: P1-03 education/tutor, P1-01/P1-08 information
  access, P1-06/P2-13 language accessibility.
- Multilingual/underserved markets are an explicit panel priority.
- Local/on-device inference strongly preferred across all RFP prose.
- AI use is effectively required (program funds AI products); any provider,
  but closed-API-only wrapper fails the openness test.
- GitHub metrics reviewed; demo links required; document upload required.
- Grant Terms are NOT public until application time (Cayman jurisdiction).
- No grantees announced yet as of 2026-08-23.

### Readiness verdict

Two hard blockers before applying:
1. No LICENSE file at repo root (legally not open source yet).
2. No deployed public demo (deploy kit exists, execution pending).

Core gaps that make the application competitive rather than weak:
3. AI explanation layer (provider-agnostic, grounded in evidence tables,
   open-weight local model default, caching by input hash per ADR patterns).
4. Ukrainian output end-to-end (`--language uk` currently fails by design).

Then: README restructure for external reviewers, one-pager PDF, repo hygiene
(CONTRIBUTING, release tag), optional 90-second walkthrough video.

Estimated total to competitive submission: ~50–80 focused hours.

### Positioning statement (draft)

Labor-market transparency for candidates the global remote market forgot:
English postings bury skill/seniority/salary signals; non-native candidates
overpay coaches or misjudge reachable roles. We extract versioned, auditable
evidence deterministically and explain it in the candidate's language using
open-weight models by default — openness is a design constraint, not a
license checkbox.

### One-line variants (≤80 chars)

- Open, private job-market evidence and skill-gap answers in your language.
- Free local-first career intelligence from live job data — open and private.
- Evidence-based remote-job skill gaps, explained in your own language.

### Risks register

- Missing LICENSE → instant credibility failure for belief #1. Fix first.
- `--language uk` fails today → never claim shipped multilingual until it runs.
- Solo-builder bus factor → mitigate by citing 800+ tests, ADR culture,
  modularity as continuity evidence.
- Counts honesty: keep posting-level caveats inside the application itself.

---

## Multilingual strategy (grant-aligned, 2026-08-23)

Multilingual does NOT mean Ukrainian-only. The foundation explicitly targets
multilingual and underserved markets; the product treats language as a
parameter, never a fork:

- Analyzer registry is keyed `kind + language`; new languages are registry
  entries, not code changes.
- The future AI explanation layer takes an output-language parameter over the
  same deterministic evidence base.
- Dashboard labels live in i18n resource files (`i18n/<locale>.json`),
  English as canonical fallback.
- Launch order follows underserved-market priorities: en (canonical core) >
  uk > es/pt (LATAM) > hi/ur > ar; each addition is data + resources, not
  architecture.
