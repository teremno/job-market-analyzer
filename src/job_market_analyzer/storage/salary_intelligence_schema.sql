CREATE TABLE IF NOT EXISTS job_salaries (
    analysis_run_id TEXT NOT NULL PRIMARY KEY,

    provenance TEXT NOT NULL,
    confidence TEXT NOT NULL,
    min_value TEXT,
    max_value TEXT,
    currency TEXT,
    period TEXT,
    annual_min TEXT,
    annual_max TEXT,
    annualized INTEGER NOT NULL,
    matched_text TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    evidence_field TEXT NOT NULL,

    FOREIGN KEY (analysis_run_id)
        REFERENCES analysis_runs(id)
        ON DELETE CASCADE,

    CHECK (provenance IN ('structured', 'text')),
    CHECK (confidence IN ('direct', 'parsed')),
    CHECK (
        (min_value IS NULL AND max_value IS NOT NULL)
        OR (min_value IS NOT NULL)
    ),
    CHECK (annualized IN (0, 1)),
    CHECK (length(trim(matched_text)) > 0),
    CHECK (length(trim(rule_id)) > 0),
    CHECK (evidence_field = 'normalized')
);


CREATE TRIGGER IF NOT EXISTS trg_job_salaries_kind
BEFORE INSERT ON job_salaries
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'salary'
BEGIN
    SELECT RAISE(ABORT, 'job_salaries requires a salary analysis run');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_salaries_kind_update
BEFORE UPDATE OF analysis_run_id ON job_salaries
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'salary'
BEGIN
    SELECT RAISE(ABORT, 'job_salaries requires a salary analysis run');
END;
