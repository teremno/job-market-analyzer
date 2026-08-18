CREATE TABLE IF NOT EXISTS skills (
    code TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL,

    CHECK (length(trim(code)) > 0),
    CHECK (length(trim(display_name)) > 0)
);


CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT NOT NULL PRIMARY KEY,

    job_posting_id TEXT NOT NULL,
    analyzer_kind TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (job_posting_id)
        REFERENCES job_postings(id)
        ON DELETE CASCADE,

    UNIQUE (
        job_posting_id,
        analyzer_kind,
        taxonomy_version,
        extractor_version,
        input_hash
    ),

    CHECK (length(trim(analyzer_kind)) > 0),
    CHECK (length(trim(taxonomy_version)) > 0),
    CHECK (length(trim(extractor_version)) > 0),
    CHECK (
        length(input_hash) = 64
        AND input_hash NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (length(trim(created_at)) > 0)
);


CREATE TABLE IF NOT EXISTS job_skills (
    analysis_run_id TEXT NOT NULL,
    skill_code TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    evidence_field TEXT NOT NULL,
    matched_alias TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    match_kind TEXT NOT NULL,
    mention_kind TEXT NOT NULL,

    PRIMARY KEY (
        analysis_run_id,
        skill_code,
        evidence_field
    ),

    FOREIGN KEY (analysis_run_id)
        REFERENCES analysis_runs(id)
        ON DELETE CASCADE,

    FOREIGN KEY (skill_code)
        REFERENCES skills(code)
        ON DELETE RESTRICT,

    CHECK (evidence_field IN ('title', 'description', 'tag')),
    CHECK (length(trim(skill_name)) > 0),
    CHECK (length(trim(matched_alias)) > 0),
    CHECK (length(trim(evidence_text)) > 0),
    CHECK (length(trim(rule_id)) > 0),
    CHECK (match_kind IN ('exact_alias', 'contextual')),
    CHECK (mention_kind = 'mentioned')
);


CREATE INDEX IF NOT EXISTS idx_analysis_runs_posting_kind_created
    ON analysis_runs(job_posting_id, analyzer_kind, created_at DESC);


CREATE INDEX IF NOT EXISTS idx_job_skills_skill_run
    ON job_skills(skill_code, analysis_run_id);
