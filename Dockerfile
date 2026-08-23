FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000

# The API reads an existing SQLite database; mount it read-only at /data.
VOLUME ["/data"]

CMD ["job-market-analyzer", "serve", "--host", "0.0.0.0", "--database", "/data/jobs.sqlite3"]
