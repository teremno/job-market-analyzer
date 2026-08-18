CREATE TABLE IF NOT EXISTS canonical_jobs (
    id TEXT NOT NULL PRIMARY KEY,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CHECK (updated_at >= created_at)
);


CREATE TABLE IF NOT EXISTS job_postings (
    id TEXT NOT NULL PRIMARY KEY,

    canonical_job_id TEXT NOT NULL,

    source_provider TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    external_id TEXT NOT NULL,

    source_url TEXT,
    application_url TEXT,

    title TEXT NOT NULL,
    company_name TEXT,
    description_text TEXT,
    source_tags_json TEXT NOT NULL DEFAULT '[]',

    location_text TEXT,
    is_remote INTEGER,
    remote_scope TEXT,

    employment_type TEXT,

    salary_text TEXT,
    salary_min TEXT,
    salary_max TEXT,
    salary_currency TEXT,
    salary_period TEXT,

    published_at TEXT,
    source_updated_at TEXT,

    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,

    content_hash TEXT NOT NULL,
    latest_observation_hash TEXT NOT NULL,

    FOREIGN KEY (canonical_job_id)
        REFERENCES canonical_jobs(id)
        ON DELETE RESTRICT,

    UNIQUE (
        source_provider,
        source_scope,
        external_id
    ),

    CHECK (length(trim(source_provider)) > 0),
    CHECK (length(trim(source_scope)) > 0),
    CHECK (length(trim(external_id)) > 0),
    CHECK (source_url IS NULL OR length(trim(source_url)) > 0),
    CHECK (length(trim(title)) > 0),
    CHECK (json_valid(source_tags_json)),
    CHECK (json_type(source_tags_json) = 'array'),

    CHECK (
        is_remote IS NULL
        OR is_remote IN (0, 1)
    ),

    CHECK (
        last_seen_at >= first_seen_at
    ),

    CHECK (
        length(content_hash) = 64
        AND content_hash NOT GLOB '*[^0-9a-f]*'
    ),

    CHECK (
        length(latest_observation_hash) = 64
        AND latest_observation_hash NOT GLOB '*[^0-9a-f]*'
    )
);


CREATE TABLE IF NOT EXISTS raw_jobs (
    id TEXT NOT NULL PRIMARY KEY,

    job_posting_id TEXT NOT NULL,

    source_provider TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    external_id TEXT NOT NULL,

    source_url TEXT,

    fetched_at TEXT NOT NULL,

    observation_hash TEXT NOT NULL,

    payload_json TEXT NOT NULL,

    FOREIGN KEY (job_posting_id)
        REFERENCES job_postings(id)
        ON DELETE RESTRICT,

    CHECK (length(trim(source_provider)) > 0),
    CHECK (length(trim(source_scope)) > 0),
    CHECK (length(trim(external_id)) > 0),
    CHECK (source_url IS NULL OR length(trim(source_url)) > 0),

    CHECK (
        length(observation_hash) = 64
        AND observation_hash NOT GLOB '*[^0-9a-f]*'
    ),

    CHECK (
        json_valid(payload_json)
    )
);


CREATE INDEX IF NOT EXISTS idx_job_postings_canonical_job_id
    ON job_postings(canonical_job_id);


CREATE INDEX IF NOT EXISTS idx_raw_jobs_posting_fetched_at
    ON raw_jobs(job_posting_id, fetched_at DESC);
