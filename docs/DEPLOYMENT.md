# Deployment Guide

This guide covers containerized self-hosting and the CI pipeline. The product
remains fully usable without Docker (see the README for the native Windows,
Linux, and macOS workflow).

## What ships today

- **API container** — the read-only FastAPI service (`job-market-analyzer serve`)
  bound to `0.0.0.0` inside the container, published only to loopback on the
  host by default.
- **Web container** — the Next.js dashboard calling the API server-side by
  service name.
- **CI** — GitHub Actions running Ruff, the full Python suite, and all
  frontend gates (lint, typecheck, unit tests, build) on every push and PR.

Not shipped yet (deliberate): public HTTPS exposure, authentication,
PostgreSQL, scheduled workers. See the roadmap before exposing anything
beyond loopback.

## Prerequisites

- Docker Engine 24+ with Compose v2 (`docker compose version`).
- A populated SQLite database file (run the guided update once on any machine
  that has network access to the sources):

```bash
pip install -e .
export WEB3_CAREER_API_TOKEN=...   # optional; missing token skips one source
job-market-analyzer update --database ./job-market.sqlite3
```

## Buying your first server (beginner walkthrough)

If you have never rented a server before, this is the whole mystery:

A **server** is just a computer in a data center that stays on 24/7. You rent
it by the month, and connect to it over the internet with SSH (a remote
terminal). Recommended spec for this product:

- **Provider:** Hetzner (hetzner.com/cloud) — or any provider offering
  "Cloud" servers.
- **Plan:** CX22 class — **2 vCPU / 4 GB RAM / 40 GB SSD**, ~€5/month.
- **Image/OS:** Ubuntu 24.04.
- **Location:** pick the region closest to your main audience (Nuremberg or
  Helsinki work well for Europe/Ukraine).
- **Authentication:** choose **SSH key** (not password) when prompted.

After purchase the panel shows the server's **public IPv4 address** — write
it down; DNS setup needs it.

### First connection (from Windows PowerShell, no extra tools needed)

```powershell
ssh root@YOUR_SERVER_IP
```

First time it asks to trust the fingerprint — type `yes`, then you are inside
the server's terminal. Everything below happens in that terminal.

### Install Docker on the server (one command)

```bash
curl -fsSL https://get.docker.com | sh
```

Verify: `docker compose version` prints a version number.

## Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

- Dashboard: <http://127.0.0.1:3000>
- API health: <http://127.0.0.1:8000/api/health>

The database is mounted read-only into the API container; the dashboard cannot
mutate your dataset.

## Refresh the data

Stop the stack, run a guided update natively (or inside a temporary
container), then start it again:

```bash
docker compose down
job-market-analyzer update --database ./job-market.sqlite3
docker compose up -d
```

## Configuration

| Variable | Where | Purpose |
|---|---|---|
| `JMA_SERVE_ALLOW_ANY_HOST=1` | api container | Explicit opt-in that lets `serve --host 0.0.0.0` bind a non-loopback interface inside the container. The CLI default remains loopback-only for local users. Never set this on a machine where port 8000 is directly internet-facing. |
| `NEXT_PUBLIC_API_BASE_URL` | web container | Base URL the dashboard's server components use to call the API. Defaults to `http://api:8000` in Compose. |
| `WEB3_CAREER_API_TOKEN` | update runs | Required only by the Web3.career source; never commit or log it. |

Host port bindings default to `127.0.0.1` so nothing is exposed to the network
by accident. To serve on a LAN/internet interface, change the binding in
`docker-compose.yml` and put a reverse proxy (Caddy/nginx) with TLS in front —
plus complete the security checklist (rate limiting, CORS origins, monitoring)
from PROJECT_HANDOFF §51 before going public.

## CI

`.github/workflows/ci.yml` runs two jobs on push/PR:

1. **python** — Python 3.13, `pip install -e ".[dev]"`, `ruff check .`,
   `python -m pytest -q`.
2. **web** — Node 22, `npm ci`, then lint, typecheck, unit tests, and build.

## Manual Docker commands (without Compose)

```bash
docker build -t jma-api .
docker run -d --name jma-api \
  -e JMA_SERVE_ALLOW_ANY_HOST=1 \
  -p 127.0.0.1:8000:8000 \
  -v "$PWD/job-market.sqlite3:/data/jobs.sqlite3:ro" \
  jma-api

docker build -t jma-web ./web
docker run -d --name jma-web \
  -p 127.0.0.1:3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://jma-api:8000 \
  --link jma-api:api \
  jma-web
```

---

## Public deployment (alpha) � step by step

Goal: a public read-only site on your own domain, served over HTTPS with
automatic certificates, from one small VPS.

### Server sizing (honest minimums)

| Resource | Alpha (up to ~100 visitors/day) | Notes |
|---|---|---|
| vCPU | 1�2 | The API is I/O-bound; analytics queries are milliseconds. |
| RAM | 2 GB works, 4 GB comfortable | api ?150 MB, web ?120 MB, Caddy ?30 MB, OS headroom. |
| Disk | 20 GB SSD | The SQLite dataset is tens of MB; logs are the only growth item. |
| OS | Ubuntu 24.04 LTS | Docker + Compose installed via the official script. |

Any provider works; Hetzner CX22-class (~�5/month) is the reference budget.
Do not buy managed databases or Kubernetes for this stage.

### Steps

1. **DNS** � in your domain registrar, point two A records at the server IP:
   `your-domain.com` and `api.your-domain.com`. Wait for propagation
   (`ping api.your-domain.com` returns your IP).
2. **Server** � install Docker:
   `curl -fsSL https://get.docker.com | sh`
3. **Get the code + data** � clone this repository, then copy your populated
   `job-market.sqlite3` to the repo root on the server (scp/rsync).
4. **Configure** � copy `.env.production.example` to `.env`, set your two
   domains. Edit `deploy/Caddyfile` placeholders if you prefer hardcoding.
5. **Start** �
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
   Caddy obtains TLS certificates automatically within a minute.
6. **Verify** � open `https://your-domain.com`; check
   `https://api.your-domain.com/api/health`.

### Updating the dataset on the server

```bash
docker compose down            # or: docker compose stop api web
job-market-analyzer update --database ./job-market.sqlite3
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The database is mounted read-only into the API container; visitors can never
mutate it.

### Security posture of this alpha

- Only ports 80/443 are exposed (Caddy); the API and dashboard containers are
  reachable through the proxy only.
- The whole product surface is GET-only against a read-only SQLite file.
- CORS allow-list defaults to localhost and must be widened explicitly per
  domain via `JMA_CORS_ORIGINS` (wildcards are ignored).
- Still required before treating it as hardened: basic rate limiting,
  log monitoring, backup automation for the SQLite file, and dependency
  scanning (PROJECT_HANDOFF �51).
