# Deployment Status — live notes

Last updated: 2026-08-23 (late night). For any agent or human continuing:
this is the exact state of the first production deployment.

## Infrastructure facts

- VPS: Hetzner CX23, 2 vCPU / 4 GB RAM / 40 GB, Ubuntu 24.04, Nuremberg.
- IP: `162.55.178.137` (SSH as root, key auth).
- Domain: `jobpulse.support` (Spaceship registrar). DNS A records for `@`,
  `api`, and `www` (CNAME) all point to the IP and are already resolving.
- Database: `job-market.sqlite3` (~7,400 postings) copied to `/root/` on the
  server. Repository cloned to `/root/job-market-analyzer/`.

## What already works

- `docker compose` stack is up: `jma-api` and `jma-web` containers are
  running healthy.
- DNS verified resolving from outside.

## What was broken and how it was fixed (2026-08-23 night)

1. Caddy container was crash-looping: `unrecognized global option:
   reverse_proxy` — caused by `DOMAIN` env being empty inside the container
   because `.env` did not exist on the server.
2. Root cause found: `.env.production.example` was never committed — the
   repo's `.gitignore` rule `.env*` silently excluded it. Fixed in commit
   `fc98f76` (gitignore exception added, template tracked).
3. `deploy/Caddyfile` also gained a `www → apex` redirect block
   (commit `0f41229`).

## Remaining steps (morning checklist)

Run on the server, inside `/root/job-market-analyzer/`:

```bash
git pull                                        # get the fixed template
cp .env.production.example .env
sed -i 's/your-domain.com/jobpulse.support/' .env
sed -i 's/api.your-domain.com/api.jobpulse.support/' .env
cat .env                                        # must show both domains
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate caddy
sleep 60                                        # Caddy fetches TLS certificates
```

Then verify from anywhere:

- https://jobpulse.support — dashboard
- https://api.jobpulse.support/api/health — must return
  `{"status":"ok","schema_version":6}`

If Caddy still fails: `docker logs jma-caddy --tail 20` and check that
`.env` contains exactly `DOMAIN=jobpulse.support` and
`API_DOMAIN=api.jobpulse.support`.

## After it is live (next backlog)

1. Auto-update worker on the server (cron/systemd timer for `update`).
2. AI explanation layer v0 (OpenAI-compatible endpoint, Groq default;
   languages = parameter, top-20 world languages; founder confirmed Groq).
3. Grant application to Sentient Foundation — see
   `docs/GRANTS_NOTES.md` (readiness plan; LICENSE blocker already resolved
   with MIT).
