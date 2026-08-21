CREATE TABLE IF NOT EXISTS roles (
    code TEXT NOT NULL PRIMARY KEY,
    display_name TEXT NOT NULL,

    CHECK (length(trim(code)) > 0),
    CHECK (length(trim(display_name)) > 0)
);


CREATE TABLE IF NOT EXISTS job_roles (
    analysis_run_id TEXT NOT NULL,
    role_code TEXT NOT NULL,
    role_name TEXT NOT NULL,
    evidence_field TEXT NOT NULL,
    matched_text TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    match_kind TEXT NOT NULL,

    PRIMARY KEY (
        analysis_run_id,
        role_code
    ),

    FOREIGN KEY (analysis_run_id)
        REFERENCES analysis_runs(id)
        ON DELETE CASCADE,

    FOREIGN KEY (role_code)
        REFERENCES roles(code)
        ON DELETE RESTRICT,

    CHECK (evidence_field IN ('title', 'description')),
    CHECK (length(trim(role_name)) > 0),
    CHECK (length(trim(matched_text)) > 0),
    CHECK (length(trim(evidence_text)) > 0),
    CHECK (length(trim(rule_id)) > 0),
    CHECK (match_kind IN ('title_pattern', 'description_statement'))
);


CREATE INDEX IF NOT EXISTS idx_job_roles_role_run
    ON job_roles(role_code, analysis_run_id);


CREATE TRIGGER IF NOT EXISTS trg_analysis_runs_identity_immutable
BEFORE UPDATE OF
    job_posting_id,
    analyzer_kind,
    taxonomy_version,
    extractor_version,
    input_hash
ON analysis_runs
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'analysis run identity is immutable');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_roles_roles_kind
BEFORE INSERT ON job_roles
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'roles'
BEGIN
    SELECT RAISE(ABORT, 'job_roles requires a roles analysis run');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_roles_roles_kind_update
BEFORE UPDATE OF analysis_run_id ON job_roles
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'roles'
BEGIN
    SELECT RAISE(ABORT, 'job_roles requires a roles analysis run');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_skills_skills_kind
BEFORE INSERT ON job_skills
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'skills'
BEGIN
    SELECT RAISE(ABORT, 'job_skills requires a skills analysis run');
END;


CREATE TRIGGER IF NOT EXISTS trg_job_skills_skills_kind_update
BEFORE UPDATE OF analysis_run_id ON job_skills
FOR EACH ROW
WHEN (
    SELECT analyzer_kind
    FROM analysis_runs
    WHERE id = NEW.analysis_run_id
) != 'skills'
BEGIN
    SELECT RAISE(ABORT, 'job_skills requires a skills analysis run');
END;
