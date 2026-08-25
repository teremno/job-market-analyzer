export type AnalysisStatus =
  | "not_analyzed"
  | "analyzed_zero"
  | "analyzed_with_results";

export interface AnalysisCounts {
  not_analyzed: number;
  analyzed_zero: number;
  analyzed_with_results: number;
}

export interface AnalysisCoverage extends AnalysisCounts {
  with_results_percentage: number;
}

export interface RoleCount { role_code: string; role_name: string; posting_count: number; }
export interface SkillCount { skill_code: string; skill_name: string; posting_count: number; }
export interface TermCount { term_code: string; term_name: string; posting_count: number; }
export interface SalaryCurrencySummary {
  currency: string;
  postings: number;
  median_annual_min: string | null;
}
export interface SourcePostingCount { source_provider: string; posting_count: number; }

export interface Overview {
  posting_count: number;
  source_count: number;
  role_analysis: AnalysisCounts;
  skill_analysis: AnalysisCounts;
  postings_by_source: SourcePostingCount[];
  top_roles: RoleCount[];
  top_skills: SkillCount[];
  top_seniority: TermCount[];
  arrangement_counts: TermCount[];
  region_counts: TermCount[];
  salary_posting_count: number;
  salary_currencies: SalaryCurrencySummary[];
}

export interface NamedRole { role_code: string; role_name: string; }
export interface NamedSkill { skill_code: string; skill_name: string; }
export interface NamedTerm { code: string; name: string; }

export interface MarketSkill {
  skill_code: string;
  skill_name: string;
  posting_count: number;
  share_of_role_postings: number;
  status: "gap" | "known";
}

export interface SkillGapReport {
  role_code: string;
  role_name: string;
  role_posting_count: number;
  known_recognized: string[];
  unknown_inputs: string[];
  gaps: MarketSkill[];
  matched_market_skills: MarketSkill[];
}

export interface Posting {
  job_posting_id: string;
  canonical_job_id: string;
  source_provider: string;
  source_scope: string;
  external_id: string;
  company_name: string | null;
  title: string;
  location: string | null;
  published_at: string | null;
  source_url: string | null;
  application_url: string | null;
  role_analysis_status: AnalysisStatus;
  skill_analysis_status: AnalysisStatus;
  roles: NamedRole[];
  skills: NamedSkill[];
  seniority?: NamedTerm | null;
  arrangement?: NamedTerm | null;
  regions?: NamedTerm[];
  salary_currency?: string | null;
  salary_annual_min?: string | null;
  salary_annual_max?: string | null;
}

export interface JobsResponse { items: Posting[]; limit: number; offset: number; total: number; }

export interface RoleDetail extends RoleCount {
  top_skills: SkillCount[];
  representative_postings: Posting[];
}

export interface SkillDetail extends SkillCount {
  associated_roles: RoleCount[];
  co_occurring_skills: SkillCount[];
  representative_postings: Posting[];
}

export type SourceUpdateStatus = "completed" | "failed" | "skipped";

// The three last_update_* fields are optional only for pre-R3 API backends;
// current backends always emit them (possibly null).
export interface SourceSummary {
  source_provider: string;
  posting_count: number;
  newest_published_at: string | null;
  newest_last_seen_at: string | null;
  role_analysis: AnalysisCoverage;
  skill_analysis: AnalysisCoverage;
  last_update_status?: SourceUpdateStatus | null;
  last_update_finished_at?: string | null;
  last_successful_update_at?: string | null;
}

export interface HealthResponse { status: string; schema_version: number; }
