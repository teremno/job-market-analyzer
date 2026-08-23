import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { isHealth, isJobsResponse, isOverview } from "./api.ts";

const analysisCounts = {
  not_analyzed: 1,
  analyzed_zero: 2,
  analyzed_with_results: 3,
};

describe("runtime API validators", () => {
  it("accepts the current overview contract", () => {
    assert.equal(isOverview({
      posting_count: 6,
      source_count: 1,
      role_analysis: analysisCounts,
      skill_analysis: analysisCounts,
      postings_by_source: [{ source_provider: "remote_ok", posting_count: 6 }],
      top_roles: [{ role_code: "backend", role_name: "Backend", posting_count: 2 }],
      top_skills: [{ skill_code: "python", skill_name: "Python", posting_count: 2 }],
      top_seniority: [{ term_code: "senior", term_name: "Senior", posting_count: 1 }],
      arrangement_counts: [
        { term_code: "arrangement_remote", term_name: "Remote", posting_count: 3 },
      ],
      region_counts: [
        { term_code: "region_worldwide", term_name: "Worldwide", posting_count: 2 },
      ],
      salary_posting_count: 4,
      salary_currencies: [
        { currency: "USD", postings: 4, median_annual_min: "120000" },
      ],
    }), true);
  });

  it("rejects non-finite counts and malformed nested rows", () => {
    assert.equal(isOverview({
      posting_count: Number.NaN,
      source_count: 1,
      role_analysis: analysisCounts,
      skill_analysis: analysisCounts,
      postings_by_source: [{ source_provider: "remote_ok", posting_count: "6" }],
      top_roles: [],
      top_skills: [],
      top_seniority: [],
      arrangement_counts: [],
      region_counts: [],
      salary_posting_count: 0,
      salary_currencies: [],
    }), false);
    assert.equal(isOverview({
      posting_count: 6,
      source_count: 1,
      role_analysis: analysisCounts,
      skill_analysis: analysisCounts,
      postings_by_source: [],
      top_roles: [],
      top_skills: [],
      top_seniority: [{ term_code: "senior", term_name: "Senior" }],
      arrangement_counts: [],
      region_counts: [],
      salary_posting_count: 0,
      salary_currencies: [],
    }), false);
  });

  it("accepts a bounded posting response and rejects invalid analysis status", () => {
    const posting = {
      job_posting_id: "posting-1",
      canonical_job_id: "canonical-1",
      source_provider: "remote_ok",
      source_scope: "global",
      external_id: "1",
      company_name: null,
      title: "Backend Engineer",
      location: null,
      published_at: null,
      source_url: "https://example.com/jobs/1",
      application_url: null,
      role_analysis_status: "analyzed_with_results",
      skill_analysis_status: "analyzed_zero",
      roles: [{ role_code: "backend", role_name: "Backend" }],
      skills: [],
    };

    assert.equal(isJobsResponse({ items: [posting], limit: 25, offset: 0, total: 1 }), true);
    assert.equal(isJobsResponse({
      items: [{ ...posting, role_analysis_status: "complete" }],
      limit: 25,
      offset: 0,
      total: 1,
    }), false);
  });

  it("validates health field types", () => {
    assert.equal(isHealth({ status: "ok", schema_version: 3 }), true);
    assert.equal(isHealth({ status: "ok", schema_version: "3" }), false);
  });
});
