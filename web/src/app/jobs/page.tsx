import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PostingsTable } from "@/components/postings";
import { SearchWithSuggestions } from "@/components/search-suggest";
import { DataError, EmptyState, PageHeader } from "@/components/ui";
import { getJobs, getOverview, getSources, loadData } from "@/lib/api";
import { formatNumber, formatProvider } from "@/lib/format";

export const metadata: Metadata = { title: "Jobs" };
const PAGE_SIZE = 25;
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function valueOf(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : "";
}

export default async function JobsPage({ searchParams }: { searchParams: SearchParams }) {
  const query = await searchParams;
  const page = Math.min(40_001, Math.max(1, Number.parseInt(valueOf(query.page), 10) || 1));
  const filters = {
    q: valueOf(query.q),
    source: valueOf(query.source),
    role: valueOf(query.role),
    skill: valueOf(query.skill),
    seniority: valueOf(query.seniority),
    geography: valueOf(query.geography),
    has_salary: valueOf(query.has_salary),
  };
  const apiParams = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
  Object.entries(filters).forEach(([key, value]) => { if (value) apiParams.set(key, value); });
  const result = await loadData(Promise.all([getJobs(apiParams), getOverview(100), getSources()]));
  if (!result.ok) {
    return <><PageHeader eyebrow="Operational browser" title="Source postings">The dashboard needs the local API to browse vacancies.</PageHeader><DataError error={result.error} /></>;
  }
  const [jobs, overview, sources] = result.data;
    const pageCount = Math.max(1, Math.ceil(jobs.total / PAGE_SIZE));
    const safePage = Math.min(page, pageCount);
    const pageHref = (nextPage: number) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
      if (nextPage > 1) params.set("page", String(nextPage));
      return `/jobs${params.size ? `?${params}` : ""}`;
    };
  if (page > pageCount) redirect(pageHref(pageCount));
  return <>
      <PageHeader eyebrow="Operational browser" title="Source postings">Search title or company, then combine source, role, skill, seniority and geography filters.</PageHeader>
      <form className="filters" action="/jobs" method="get">
        <SearchWithSuggestions
          key={`${filters.q}|${filters.skill}|${filters.role}|${filters.source}|${filters.seniority}|${filters.geography}|${filters.has_salary}`}
          defaultValue={filters.q}
          skills={overview.top_skills}
          roles={overview.top_roles}
          currentFilters={{
            source: filters.source,
            role: filters.role,
            skill: filters.skill,
            seniority: filters.seniority,
            geography: filters.geography,
            has_salary: filters.has_salary,
          }}
        />
        <label><span>Source</span><select name="source" defaultValue={filters.source}><option value="">All sources</option>{sources.map((source) => <option key={source.source_provider} value={source.source_provider}>{formatProvider(source.source_provider)} ({source.posting_count})</option>)}</select></label>
        <label><span>Role</span><select name="role" defaultValue={filters.role}><option value="">All analyzed roles</option>{overview.top_roles.map((role) => <option key={role.role_code} value={role.role_code}>{role.role_name} ({role.posting_count})</option>)}</select></label>
        <label><span>Skill</span><select name="skill" defaultValue={filters.skill}><option value="">All mentioned skills</option>{overview.top_skills.map((skill) => <option key={skill.skill_code} value={skill.skill_code}>{skill.skill_name} ({skill.posting_count})</option>)}</select></label>
        <label><span>Seniority</span><select name="seniority" defaultValue={filters.seniority}><option value="">Any seniority</option>{overview.top_seniority.map((term) => <option key={term.term_code} value={term.term_code}>{term.term_name} ({term.posting_count})</option>)}</select></label>
        <label><span>Geography</span><select name="geography" defaultValue={filters.geography}><option value="">Any geography</option>{[...overview.arrangement_counts, ...overview.region_counts].map((term) => <option key={term.term_code} value={term.term_code}>{term.term_name} ({term.posting_count})</option>)}</select></label>
        <label><span>Salary</span><select name="has_salary" defaultValue={filters.has_salary}><option value="">With or without salary</option><option value="true">Only with salary estimate</option></select></label>
        <div className="filter-actions"><button type="submit">Apply filters</button>
          {/* Deliberately a plain anchor, not <Link>: a full document load is
              required to reset the uncontrolled form controls. */}
          <a href="/jobs">Clear filters</a>
        </div>
      </form>
      <div className="result-summary" aria-live="polite"><p><strong>{formatNumber(jobs.total)}</strong> matching source postings</p>{jobs.total > 0 && <span>Showing {formatNumber(jobs.offset + 1)}–{formatNumber(Math.min(jobs.offset + jobs.items.length, jobs.total))}</span>}</div>
      {jobs.items.length ? <PostingsTable postings={jobs.items} /> : <EmptyState title="No postings match these filters.">Clear one or more filters, or try a broader title/company search.</EmptyState>}
      {jobs.total > 0 && <nav className="pagination" aria-label="Job pages">{safePage <= 1 ? <span className="pagination-control pagination-disabled" aria-disabled="true">Previous</span> : <Link className="pagination-control" href={pageHref(safePage - 1)}>Previous</Link>}<span>Page {safePage} of {pageCount}</span>{safePage >= pageCount ? <span className="pagination-control pagination-disabled" aria-disabled="true">Next</span> : <Link className="pagination-control" href={pageHref(safePage + 1)}>Next</Link>}</nav>}
  </>;
}
