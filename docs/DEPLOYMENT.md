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
