CREATE TABLE IF NOT EXISTS source_update_runs (
    id INTEGER NOT NULL PRIMARY KEY,

    source_provider TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,

    fetched_count INTEGER,
    persisted_count INTEGER,
    failed_count INTEGER,

    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,

    CHECK (status IN ('completed', 'failed', 'skipped')),
    CHECK (length(trim(source_provider)) > 0),
    CHECK (length(trim(display_name)) > 0),
    CHECK (message IS NULL OR length(trim(message)) > 0),
    CHECK (
        (status = 'completed'
            AND fetched_count IS NOT NULL
            AND persisted_count IS NOT NULL
            AND failed_count IS NOT NULL)
        OR (status != 'completed'
            AND fetched_count IS NULL
            AND persisted_count IS NULL
            AND failed_count IS NULL)
    ),
    CHECK (finished_at >= started_at)
);


CREATE INDEX IF NOT EXISTS idx_source_update_runs_provider_finished
    ON source_update_runs (source_provider, finished_at);
