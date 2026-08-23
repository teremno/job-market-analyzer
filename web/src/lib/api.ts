import type {
  HealthResponse,
  JobsResponse,
  Overview,
  RoleDetail,
  SkillDetail,
  SkillGapReport,
  SourceSummary,
} from "@/lib/types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 15_000;
type ApiErrorKind = "unavailable" | "not_found" | "invalid_response" | "api";

export class ApiClientError extends Error {
  public readonly kind: ApiErrorKind;
  public readonly status?: number;

  constructor(
    kind: ApiErrorKind,
    message: string,
    status?: number,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.kind = kind;
    this.status = status;
  }
}

export type LoadResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: unknown };

export async function loadData<T>(promise: Promise<T>): Promise<LoadResult<T>> {
  try {
    return { ok: true, data: await promise };
  } catch (error) {
    return { ok: false, error };
  }
}

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasNumber(value: Record<string, unknown>, key: string): boolean {
  return typeof value[key] === "number" && Number.isFinite(value[key]);
}

function hasString(value: Record<string, unknown>, key: string): boolean {
  return typeof value[key] === "string";
}

function hasNullableString(value: Record<string, unknown>, key: string): boolean {
  return value[key] === null || typeof value[key] === "string";
}

function isAnalysisCounts(value: unknown): boolean {
  return isRecord(value) && hasNumber(value, "not_analyzed")
    && hasNumber(value, "analyzed_zero") && hasNumber(value, "analyzed_with_results");
}

function isAnalysisCoverage(value: unknown): boolean {
  return isAnalysisCounts(value) && isRecord(value)
    && hasNumber(value, "with_results_percentage");
}

function isRoleCount(value: unknown): boolean {
  return isRecord(value) && hasString(value, "role_code")
    && hasString(value, "role_name") && hasNumber(value, "posting_count");
}

function isSkillCount(value: unknown): boolean {
  return isRecord(value) && hasString(value, "skill_code")
    && hasString(value, "skill_name") && hasNumber(value, "posting_count");
}

function isSourceCount(value: unknown): boolean {
  return isRecord(value) && hasString(value, "source_provider")
    && hasNumber(value, "posting_count");
}

function isNamedRole(value: unknown): boolean {
  return isRecord(value) && hasString(value, "role_code") && hasString(value, "role_name");
}

function isNamedSkill(value: unknown): boolean {
  return isRecord(value) && hasString(value, "skill_code") && hasString(value, "skill_name");
}

function isTermCount(value: unknown): boolean {
  return isRecord(value) && hasString(value, "term_code")
    && hasString(value, "term_name") && hasNumber(value, "posting_count");
}

function isSalaryCurrencySummary(value: unknown): boolean {
  return isRecord(value) && hasString(value, "currency")
    && hasNumber(value, "postings")
    && hasNullableString(value, "median_annual_min");
}

function isNamedTerm(value: unknown): boolean {
  return isRecord(value) && hasString(value, "code") && hasString(value, "name");
}

function hasFiniteString(value: Record<string, unknown>, key: string): boolean {
  if (value[key] === null) return true;
  if (typeof value[key] !== "string") return false;
  const parsed = Number(value[key]);
  return Number.isFinite(parsed);
}

function isAnalysisStatus(value: unknown): boolean {
  return value === "not_analyzed" || value === "analyzed_zero"
    || value === "analyzed_with_results";
}

export function isOverview(value: unknown): value is Overview {
  if (!isRecord(value)) return false;
  return hasNumber(value, "posting_count") && hasNumber(value, "source_count")
    && isAnalysisCounts(value.role_analysis) && isAnalysisCounts(value.skill_analysis)
    && Array.isArray(value.postings_by_source) && value.postings_by_source.every(isSourceCount)
    && Array.isArray(value.top_roles) && value.top_roles.every(isRoleCount)
    && Array.isArray(value.top_skills) && value.top_skills.every(isSkillCount)
    && Array.isArray(value.top_seniority) && value.top_seniority.every(isTermCount)
    && Array.isArray(value.arrangement_counts) && value.arrangement_counts.every(isTermCount)
    && Array.isArray(value.region_counts) && value.region_counts.every(isTermCount)
    && hasNumber(value, "salary_posting_count")
    && Array.isArray(value.salary_currencies) && value.salary_currencies.every(isSalaryCurrencySummary);
}

function isPosting(value: unknown): boolean {
  return isRecord(value) && hasString(value, "job_posting_id")
    && hasString(value, "canonical_job_id") && hasString(value, "source_provider")
    && hasString(value, "source_scope") && hasString(value, "external_id")
    && hasNullableString(value, "company_name") && hasString(value, "title")
    && hasNullableString(value, "location") && hasNullableString(value, "published_at")
    && hasNullableString(value, "source_url") && hasNullableString(value, "application_url")
    && isAnalysisStatus(value.role_analysis_status)
    && isAnalysisStatus(value.skill_analysis_status)
    && Array.isArray(value.roles) && value.roles.every(isNamedRole)
    && Array.isArray(value.skills) && value.skills.every(isNamedSkill)
    && (value.seniority === null || value.seniority === undefined || isNamedTerm(value.seniority))
    && (value.arrangement === null || value.arrangement === undefined || isNamedTerm(value.arrangement))
    && (value.regions === null || value.regions === undefined
      || (Array.isArray(value.regions) && value.regions.every(isNamedTerm)))
    && (!("salary_currency" in value) || hasNullableString(value, "salary_currency"))
    && (!("salary_annual_min" in value) || hasFiniteString(value, "salary_annual_min"))
    && (!("salary_annual_max" in value) || hasFiniteString(value, "salary_annual_max"));
}

export function isJobsResponse(value: unknown): value is JobsResponse {
  return isRecord(value) && Array.isArray(value.items) && value.items.every(isPosting)
    && hasNumber(value, "limit") && hasNumber(value, "offset") && hasNumber(value, "total");
}

export function isRoleDetail(value: unknown): value is RoleDetail {
  return isRecord(value) && hasString(value, "role_code") && hasString(value, "role_name")
    && hasNumber(value, "posting_count") && Array.isArray(value.top_skills)
    && value.top_skills.every(isSkillCount)
    && Array.isArray(value.representative_postings)
    && value.representative_postings.every(isPosting);
}

export function isSkillDetail(value: unknown): value is SkillDetail {
  return isRecord(value) && hasString(value, "skill_code") && hasString(value, "skill_name")
    && hasNumber(value, "posting_count") && Array.isArray(value.associated_roles)
    && value.associated_roles.every(isRoleCount)
    && Array.isArray(value.co_occurring_skills) && value.co_occurring_skills.every(isSkillCount)
    && Array.isArray(value.representative_postings)
    && value.representative_postings.every(isPosting);
}

export function isSourceSummary(value: unknown): value is SourceSummary {
  return isRecord(value) && hasString(value, "source_provider")
    && hasNumber(value, "posting_count") && hasString(value, "newest_last_seen_at")
    && hasNullableString(value, "newest_published_at")
    && isAnalysisCoverage(value.role_analysis) && isAnalysisCoverage(value.skill_analysis);
}

export function isHealth(value: unknown): value is HealthResponse {
  return isRecord(value) && hasString(value, "status") && hasNumber(value, "schema_version");
}

async function requestJson<T>(path: string, validate: (value: unknown) => value is T): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    throw new ApiClientError("unavailable", "The local API could not be reached.");
  }
  if (!response.ok) {
    throw new ApiClientError(
      response.status === 404 ? "not_found" : "api",
      `The local API returned HTTP ${response.status}.`,
      response.status,
    );
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiClientError("invalid_response", "The local API returned invalid JSON.");
  }
  if (!validate(payload)) {
    throw new ApiClientError("invalid_response", "The local API response does not match the dashboard contract.");
  }
  return payload;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson("/api/health", isHealth);
}

export function getSkillGap(role: string, skills: string): Promise<SkillGapReport> {
  const params = new URLSearchParams({ role });
  if (skills) params.set("skills", skills);
  return requestJson(`/api/skill-gap?${params.toString()}`, (value): value is SkillGapReport => {
    if (!isRecord(value) || !hasString(value, "role_code") || !hasString(value, "role_name")
      || !hasNumber(value, "role_posting_count")) {
      return false;
    }
    const isMarket = (item: unknown): boolean =>
      isRecord(item) && hasString(item, "skill_code") && hasString(item, "skill_name")
      && hasNumber(item, "posting_count") && hasNumber(item, "share_of_role_postings")
      && (item.status === "gap" || item.status === "known");
    const isStringArray = (item: unknown): boolean =>
      Array.isArray(item) && item.every((v): v is string => typeof v === "string");
    return isStringArray(value.known_recognized)
      && isStringArray(value.unknown_inputs)
      && Array.isArray(value.gaps) && value.gaps.every(isMarket)
      && Array.isArray(value.matched_market_skills)
      && value.matched_market_skills.every(isMarket);
  });
}

export function getOverview(topLimit = 10): Promise<Overview> {
  return requestJson(`/api/overview?top_limit=${topLimit}`, isOverview);
}

export function getJobs(params: URLSearchParams): Promise<JobsResponse> {
  return requestJson(`/api/jobs?${params.toString()}`, isJobsResponse);
}

export function getRole(code: string): Promise<RoleDetail> {
  return requestJson(`/api/roles/${encodeURIComponent(code)}`, isRoleDetail);
}

export function getSkill(code: string): Promise<SkillDetail> {
  return requestJson(`/api/skills/${encodeURIComponent(code)}`, isSkillDetail);
}

export function getSources(): Promise<SourceSummary[]> {
  return requestJson("/api/sources", (value): value is SourceSummary[] =>
    Array.isArray(value) && value.every(isSourceSummary));
}
