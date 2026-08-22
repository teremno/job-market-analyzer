CREATE TABLE IF NOT EXISTS seniority_levels (
    code TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL,

    CHECK (length(trim(code)) > 0),
    CHECK (length(trim(display_name)) > 0)
);


CREATE TABLE IF NOT EXISTS job_seniority (
    analysis_run_id TEXT NOT NULL,
    seniority_code TEXT NOT NULL,
    seniority_name TEXT NOT NULL,
    evidence_field TEXT NOT NULL,
    matched_text TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    match_kind TEXT NOT NULL,

    PRIMARY KEY (
        analysis_run_id,
        seniority_code
    ),

    FOREIGN KEY (analysis_run_id)
        REFERENCES analysis_runs(id)
        ON DELETE CASCADE,

    FOREIGN KEY (seniority_code)
        REFERENCES seniority_levels(code)
        ON DELETE RESTRICT,

    CHECK (evidence_field IN ('title', 'description')),
    CHECK (length(trim(seniority_name)) > 0),
    CHECK (length(trim(matched_text)) > 0),
    CHECK (length(trim(evidence_text)) > 0),
    CHECK (length(trim(rule_id)) > 0),
    CHECK (match_kind IN ('title_pattern', 'description_statement'))
);


CREATE INDEX IF NOT EXISTS idx_job_seniority_level_run
    ON job_seniority(seniority_code, analysis_run_id);


CREATE TRIGGER IF NOT EXISTS trg_job_seniority_levels_kind
BEFORE INSERT ON job_seniority
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'seniority'
BEGIN
    SELECT RAISE(ABORT, 'job_seniority requires a seniority analysis run');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_seniority_levels_kind_update
BEFORE UPDATE OF analysis_run_id ON job_seniority
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'seniority'
BEGIN
    SELECT RAISE(ABORT, 'job_seniority requires a seniority analysis run');
END;
