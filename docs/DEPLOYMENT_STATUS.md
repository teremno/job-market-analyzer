# JobPulse — Deployment Status & Memory
# Last updated: 2026-08-24, end of 2-day intensive sprint
# For any agent or human continuing: this is the COMPLETE state.

## PROJECT IDENTITY

- Product name: **JobPulse** (working brand; repo name stays job-market-analyzer)
- Domain: **https://jobpulse.support** (LIVE, HTTPS via Caddy auto-TLS)
- API: **https://api.jobpulse.support** (schema v6)
- License: **MIT** (LICENSE file at root)
- Grant target: **Sentient Foundation Open Source AGI Grant** (rolling, no deadline)
  - See docs/GRANTS_NOTES.md for full research + readiness plan

## CURRENT DATASET (as of 2026-08-24)

- **10,451 source postings** across **11 platforms**
- Platforms: Remote OK, Web3.career, Himalayas, Jobicy, Remotive,
  We Work Remotely, Greenhouse (36 boards), Lever (2 boards),
  Ashby (28 boards, with compensation), The Muse (public API), Adzuna (GB+US)
- 5 intelligence dimensions: skills, roles, seniority, geography, salary
- Skill taxonomy: **v5, 122 canonical skills** (96.2% ESCO/O*NET coverage)
- Role taxonomy: **v3, 21 role codes** (47.7% classification coverage on the
  live dataset, up from 40.5%; gold-set FP/FN gate added per R2)
- SQLite schema: **v7** (v6 + source_update_runs history; server DB migrates
  on first updater run)
- Tests: **909 passed**, ruff clean, frontend gates clean, CI green (tri-OS)

## SERVER

- VPS: Hetzner CX23, 2 vCPU / 4 GB RAM / 40 GB, Ubuntu 24.04, Nuremberg
- IP: **162.55.178.137** (SSH as root, key auth)
- Docker Compose stack: api + web + caddy (auto-TLS)
- Database: /root/job-market-analyzer/job-market.sqlite3 (read-only mount)
- DNS: A records @ and api → 162.55.178.137 (Spaceship registrar)

## ENVIRONMENT VARIABLES (user-level on Windows, set via setx)

- WEB3_CAREER_API_TOKEN — Web3.career source
- ADZUNA_APP_ID = 1a4b9b99
- ADZUNA_APP_KEY = (set, 32 hex chars)
- THE_MUSE_API_KEY — optional (works without, 500 req/hr anonymous)
- JMA_SERVE_ALLOW_ANY_HOST — server-side only (Dockerfile sets it)

## WHAT WAS ACCOMPLISHED (2-day sprint, ~25 commits)

### Day 1 (2026-08-22)
- Block 0: Docs sync, ADR-019 (accounts after alpha), ADR-020 (lifecycle not deletion)
- Block 1: First real 9-source update + data audit → DATA_QUALITY_NOTES.md
- Web3.career token fixed (user regenerated)
- Block 2: Job Lifecycle v1 (30-day freshness, include_stale param)
- Block 3: Greenhouse ATS (16→36 boards)
- Role Taxonomy v2 (coverage 32.9%→45.6%)
- Seniority v1 (schema v4, title-only)
- Geography v1 (schema v5, arrangement + region)
- Lever + Ashby sources (+2677 postings)
- Salary v1 (schema v6, structured + text parsing)
- Dashboard v2 (all intelligence exposed in UI)
- Full audit (3 agents)
- Skill Gap v1 (CLI + API + /gap page)
- Search autocomplete + role families UX
- Tri-agent review (Clear filters bug, taxonomy FP guards, missing LICENSE)
- Taxonomy v5 (contextual guards hardening)
- The Muse + Adzuna sources
- ESCO/O*NET validation (96.2% coverage)
- Production deployment (jobpulse.support live)
- Self-reflection report (docs/SELF_REFLECTION.md)

### Key metrics achieved
- Postings: 532 → **10,451**
- Sources: 6 → **11**
- Skill taxonomy: 60 → **122** (v2 → v5)
- Role coverage: 32.9% → **45.6%**
- Geography coverage: **86%**
- Salary coverage: 104 → **1,481**
- Tests: 731 → **858**
- ESCO/O*NET validation: **96.2%**

## ARCHITECTURE DECISIONS (ADRs)

- ADR-019: Optional accounts ONLY after hosted alpha
- ADR-020: Retention = lifecycle status, NOT deletion
- ADR-021: Role Taxonomy v2 (mined from Unknown titles)
- ADR-022: Seniority v1 (title-only, experience-axis)
- ADR-023: Geography v1 (arrangement + region)
- ADR-024: Salary v1 (structured + text, conservative)
- ADR-025: Skill Gap v1 (read-only calculator)
- ADR-026: Ashby compensation enabled
- ADR-027: Skill Taxonomy v3 (marketing family)
- ADR-028: Skill Taxonomy v4→v5 (all families + guards)

## CRITICAL INVARIANTS (do not break)

1. Posting identity: (source_provider, source_scope, external_id)
2. Arrival-order raw observations + event-time freshness
3. Deterministic serialization (UTC format, canonical JSON, 64-hex hashes)
4. Idempotency of updates and analysis runs
5. Exact-current resolution by input_hash + version (NEVER MAX(created_at))
6. Analyzer-kind isolation (schema triggers)
7. Historical run retention (no deletes)
8. Read-only API connections (mode=ro, query_only, per-request)
9. Secret redaction (tokens never logged)
10. Posting-level honesty ("source postings" not "unique jobs")

## TOP 5 NEXT RECOMMENDATIONS (from self-reflection)

### R1. Make deployment rehearseable
Add to CI: compose config validation, env-var check, deploy smoke script.

### R2. Gate taxonomy revisions with gold-set FP/FN suite
Each ambiguous alias gets positive/negative/guard test cases.
No version bump ships unless the suite passes.

### R3. Production update worker + source health visibility
Systemd timer running `update` against the server DB.
Expose "last successful update per source" on the Sources page.
**STATUS (2026-08-25): CODE COMPLETE** — schema v7 `source_update_runs`
(append-only attempt history), orchestrator records every attempt,
`/api/sources` + Sources page expose last success/latest attempt,
`docker-compose.worker.yml` + `deploy/systemd/jma-update.*` shipped
(docs/DEPLOYMENT.md → "Automated updates"). **REMAINING:** activate on the
server (git pull, build updater, put creds in `.env`, enable timer) — the
live site still serves a frozen snapshot until then.

### R4. Fix documentation integrity mechanically
UTF-8 conformance check in CI. Pre-commit hook rejecting stray files.
PROJECT_HANDOFF.md still has ~78 residual mojibake sequences.

### R5. Security sprint before surface growth
Rate limiting, auth scoping, salary presentation caveat,
canonical dedup v1 scoping.

## NEXT STEPS (in priority order)

1. **Activate R3 on the server**: DONE 2026-08-25 — timer live, daily
   04:03 UTC; first run 11/11 sources, 0 failures
2. **ESCO validation expansion**: roles v3 DONE 2026-08-25 (+gold-set gate
   closes R2 for roles); remaining: deeper skills-vs-ESCO per family
3. **Adzuna live smoke**: DONE via first timer run (200 fetched)
5. **The Muse API key** (optional, register at themuse.com/developers/api/v2/apps)
6. **Grant application** to Sentient Foundation (see docs/GRANTS_NOTES.md)
7. **Multilingual AI layer** (top-25 world languages, Groq/OpenRouter)
8. **User profiles** (localStorage first, accounts later per ADR-019)

## KEY FILES FOR NEW AGENTS

- PROJECT_HANDOFF.md — full handoff (3000+ lines, comprehensive)
- docs/DEPLOYMENT_STATUS.md — server state + morning checklist
- docs/DEPLOYMENT.md — deployment guide (beginner walkthrough included)
- docs/GRANTS_NOTES.md — Sentient Foundation research + readiness plan
- docs/TAXONOMY_VALIDATION.md — ESCO/O*NET validation report
- docs/SELF_REFLECTION.md — bug patterns, process lessons, recommendations
- docs/DATA_QUALITY_NOTES.md — data audit findings
- docs/ARCHITECTURE.md — system architecture
- docs/DECISIONS.md — ADR-001 through ADR-028
- docs/ROADMAP.md — current roadmap with status

## COMMANDS QUICK REFERENCE

### Local (PowerShell, from repo root, ALWAYS use venv)
.\.venv\Scripts\job-market-analyzer.exe update --database .\job-market.sqlite3
.\.venv\Scripts\job-market-analyzer.exe skill-gap --database .\job-market.sqlite3 --role backend --skills python,sql
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .

### Server (SSH: ssh root@162.55.178.137)
cd /root/job-market-analyzer && git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api web
docker compose restart api web
docker logs jma-api --tail 20

### Database sync (local → server)
scp .\job-market.sqlite3 root@162.55.178.137:/root/job-market-analyzer/job-market.sqlite3
# Then on server: docker compose restart api web
