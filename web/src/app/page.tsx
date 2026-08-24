import type { Metadata } from "next";
import Link from "next/link";

import { BarList, Coverage, DataError, MetricCard, PageHeader } from "@/components/ui";
import { getOverview, loadData } from "@/lib/api";
import { formatNumber, percentage, formatProvider } from "@/lib/format";

export const metadata: Metadata = { title: "Overview" };

export default async function OverviewPage() {
  const result = await loadData(getOverview());
  if (!result.ok) {
    return <><PageHeader eyebrow="Local dataset" title="Market overview">The dashboard needs the local API to read persisted data.</PageHeader><DataError error={result.error} /></>;
  }
  const data = result.data;
    const roleCoverage = percentage(data.role_analysis.analyzed_with_results + data.role_analysis.analyzed_zero, data.posting_count);
    const skillCoverage = percentage(data.skill_analysis.analyzed_with_results + data.skill_analysis.analyzed_zero, data.posting_count);
    const maxSource = Math.max(...data.postings_by_source.map((item) => item.posting_count), 1);
  return <>
      <PageHeader eyebrow="Local dataset / snapshot" title="Market overview">A factual view of persisted source postings and current deterministic analysis.</PageHeader>
      <section className="metrics-grid" aria-label="Dataset summary">
        <MetricCard label="Source postings" value={data.posting_count} note="Not cross-source deduplicated" />
        <MetricCard label="Observed sources" value={data.source_count} note="In this local database" />
        <MetricCard label="Role analyzed" value={`${roleCoverage}%`} note={`${formatNumber(data.posting_count - data.role_analysis.not_analyzed)} of ${formatNumber(data.posting_count)}`} />
        <MetricCard label="Skill analyzed" value={`${skillCoverage}%`} note={`${formatNumber(data.posting_count - data.skill_analysis.not_analyzed)} of ${formatNumber(data.posting_count)}`} />
      </section>
      <section className="coverage-grid"><Coverage title="Role analysis coverage" counts={data.role_analysis} zeroLabel="Analyzed Unknown" /><Coverage title="Skill analysis coverage" counts={data.skill_analysis} zeroLabel="Analyzed zero" /></section>
      <section className="insight-grid">
        <article className="panel"><div className="panel-heading"><div><p className="eyebrow">Current evidence</p><h2>Top roles</h2></div><Link href="/roles">Explore all</Link></div><BarList kind="roles" items={data.top_roles.map((r) => ({ code: r.role_code, name: r.role_name, count: r.posting_count }))} /></article>
        <article className="panel"><div className="panel-heading"><div><p className="eyebrow">Direct mentions</p><h2>Top skills</h2></div><Link href="/skills">Explore all</Link></div><BarList kind="skills" items={data.top_skills.map((s) => ({ code: s.skill_code, name: s.skill_name, count: s.posting_count }))} /></article>
      </section>
      <section className="insight-grid">
        <article className="panel"><div className="panel-heading"><div><p className="eyebrow">Experience axis</p><h2>Seniority signals</h2></div><Link href="/jobs?seniority=senior">Filter jobs</Link></div><BarList kind="roles" linkTemplate="/jobs?seniority={code}" items={data.top_seniority.map((s) => ({ code: s.term_code, name: s.term_name, count: s.posting_count }))} /></article>
        <article className="panel"><div className="panel-heading"><div><p className="eyebrow">Work arrangement</p><h2>Remote / hybrid / onsite</h2></div><Link href="/jobs?geography=arrangement_remote">Remote jobs</Link></div><BarList kind="roles" linkTemplate="/jobs?geography={code}" items={data.arrangement_counts.map((a) => ({ code: a.term_code, name: a.term_name, count: a.posting_count }))} /></article>
      </section>
      <section className="insight-grid">
        <article className="panel"><div className="panel-heading"><div><p className="eyebrow">Eligibility</p><h2>Regions</h2></div><Link href="/jobs?geography=region_worldwide">Worldwide</Link></div><BarList kind="roles" linkTemplate="/jobs?geography={code}" items={data.region_counts.map((r) => ({ code: r.term_code, name: r.term_name, count: r.posting_count }))} /></article>
        <article className="panel"><div className="panel-heading"><div><p className="eyebrow">Compensation</p><h2>Salary estimates</h2></div><Link href="/jobs?has_salary=true">With salary</Link></div>
          {data.salary_currencies.length ? (
            <ul>{data.salary_currencies.map((item) => {
              const median = item.median_annual_min !== null && Number.isFinite(Number(item.median_annual_min))
                ? formatNumber(Number(item.median_annual_min))
                : null;
              return <li key={item.currency}><strong>{item.currency}</strong><span>{formatNumber(item.postings)} postings</span><b>{median ? `median from ${median}` : "no annual data"}</b></li>;
            })}</ul>
          ) : (
            <p className="muted">No salary estimates in the active dataset yet.</p>
          )}
        </article>
      </section>
      <section className="panel source-overview"><div className="panel-heading"><div><p className="eyebrow">Dataset composition</p><h2>Source postings</h2></div><Link href="/sources">Source details</Link></div>
        <ul>{data.postings_by_source.map((source) => <li key={source.source_provider}><strong>{formatProvider(source.source_provider)}</strong><span><i style={{ width: `${(source.posting_count / maxSource) * 100}%` }} /></span><b>{formatNumber(source.posting_count)}</b></li>)}</ul>
      </section>
  </>;
}
