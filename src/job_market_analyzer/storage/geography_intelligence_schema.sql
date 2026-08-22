CREATE TABLE IF NOT EXISTS geography_terms (
    code TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL,
    dimension TEXT NOT NULL,

    CHECK (length(trim(code)) > 0),
    CHECK (length(trim(display_name)) > 0),
    CHECK (dimension IN ('arrangement', 'region'))
);


CREATE TABLE IF NOT EXISTS job_geography (
    analysis_run_id TEXT NOT NULL,
    geography_code TEXT NOT NULL,
    geography_name TEXT NOT NULL,
    dimension TEXT NOT NULL,
    evidence_field TEXT NOT NULL,
    matched_text TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    match_kind TEXT NOT NULL,

    PRIMARY KEY (
        analysis_run_id,
        geography_code
    ),

    FOREIGN KEY (analysis_run_id)
        REFERENCES analysis_runs(id)
        ON DELETE CASCADE,

    FOREIGN KEY (geography_code)
        REFERENCES geography_terms(code)
        ON DELETE RESTRICT,

    CHECK (dimension IN ('arrangement', 'region')),
    CHECK (evidence_field IN ('description', 'location', 'structured')),
    CHECK (length(trim(geography_name)) > 0),
    CHECK (length(trim(matched_text)) > 0),
    CHECK (length(trim(evidence_text)) > 0),
    CHECK (length(trim(rule_id)) > 0),
    CHECK (
        match_kind IN ('title_pattern', 'description_statement', 'normalized_field')
    )
);


CREATE INDEX IF NOT EXISTS idx_job_geography_term_run
    ON job_geography(geography_code, analysis_run_id);


CREATE TRIGGER IF NOT EXISTS trg_job_geography_terms_kind
BEFORE INSERT ON job_geography
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'geography'
BEGIN
    SELECT RAISE(ABORT, 'job_geography requires a geography analysis run');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_geography_terms_kind_update
BEFORE UPDATE OF analysis_run_id ON job_geography
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'geography'
BEGIN
    SELECT RAISE(ABORT, 'job_geography requires a geography analysis run');
END;
