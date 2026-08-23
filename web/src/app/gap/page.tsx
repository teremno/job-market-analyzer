import type { Metadata } from "next";
import Link from "next/link";

import { BarList, DataError, PageHeader } from "@/components/ui";
import { getOverview, getSkillGap, loadData } from "@/lib/api";
import { formatNumber, formatPercentage } from "@/lib/format";

export const metadata: Metadata = { title: "Skill gap" };
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function valueOf(value: string | string[] | undefined): string {
  return typeof value === "string" ? value : "";
}

export default async function SkillGapPage({ searchParams }: { searchParams: SearchParams }) {
  const query = await searchParams;
  const role = valueOf(query.role);
  const skills = valueOf(query.skills);
  const hasQuery = role.trim().length > 0;

  const overviewResult = await loadData(getOverview(100));
  if (!overviewResult.ok) {
    return <><PageHeader eyebrow="Personal intelligence" title="Skill gap">The dashboard needs the local API to compute a gap.</PageHeader><DataError error={overviewResult.error} /></>;
  }
  const overview = overviewResult.data;

  if (!hasQuery) {
    return <>
      <PageHeader eyebrow="Personal intelligence" title="Skill gap">Pick a target role and list the skills you already have. The calculator ranks what the active market mentions for that role and splits it into gaps and matches.</PageHeader>
      <form className="filters" action="/gap" method="get">
        <label><span>Target role</span>
          <select name="role" defaultValue="" required>
            <option value="" disabled>Select a role</option>
            {overview.top_roles.map((item) => (
              <option key={item.role_code} value={item.role_code}>{item.role_name} ({item.posting_count})</option>
            ))}
          </select>
        </label>
        <label className="search-field"><span>Your skills</span>
          <input type="search" name="skills" placeholder="python, sql, Docker" maxLength={500} />
        </label>
        <div className="filter-actions"><button type="submit">Compute gap</button></div>
      </form>
      <p className="muted">Skills are matched case-insensitively by canonical code or display name. Unrecognized inputs are reported back honestly.</p>
    </>;
  }

  const gapResult = await loadData(getSkillGap(role, skills));
  if (!gapResult.ok) {
    return <>
      <PageHeader eyebrow="Personal intelligence" title="Skill gap">Could not compute the gap for this role.</PageHeader>
      <DataError error={gapResult.error} />
      <p><Link href="/gap">← Try another role</Link></p>
    </>;
  }
  const report = gapResult.data;

  return <>
    <PageHeader eyebrow="Personal intelligence" title={`Skill gap · ${report.role_name}`}>
      Based on {formatNumber(report.role_posting_count)} active postings classified with this role.
      Evidence is mention-level — a skill being mentioned is not proof that it is required.
    </PageHeader>

    {(report.unknown_inputs.length > 0 || report.known_recognized.length > 0) && (
      <section className="panel">
        <div className="panel-heading"><div><p className="eyebrow">Your input</p><h2>Recognized skills</h2></div><Link href="/gap">New calculation</Link></div>
        {report.known_recognized.length > 0
          ? <p>{report.known_recognized.map((code) => <span key={code} className="source-pill">{code}</span>)}</p>
          : <p className="muted">None of your inputs matched the taxonomy.</p>}
        {report.unknown_inputs.length > 0 && (
          <p>Not recognized and ignored: <em>{report.unknown_inputs.join(", ")}</em></p>
        )}
      </section>
    )}

    <section className="insight-grid">
      <article className="panel">
        <div className="panel-heading"><div><p className="eyebrow">Market evidence</p><h2>Gaps to consider</h2></div></div>
        {report.gaps.length ? (
          <BarList kind="skills" items={report.gaps.slice(0, 15).map((entry) => ({
            code: entry.skill_code,
            name: `${entry.skill_name} · ${formatPercentage(entry.share_of_role_postings)}`,
            count: entry.posting_count,
          }))} />
        ) : (
          <p className="muted">No unclaimed market skills in the current evidence window.</p>
        )}
      </article>
      <article className="panel">
        <div className="panel-heading"><div><p className="eyebrow">Already on your list</p><h2>Matches in this market</h2></div></div>
        {report.matched_market_skills.length ? (
          <BarList kind="skills" items={report.matched_market_skills.slice(0, 15).map((entry) => ({
            code: entry.skill_code,
            name: `${entry.skill_name} · ${formatPercentage(entry.share_of_role_postings)}`,
            count: entry.posting_count,
          }))} />
        ) : (
          <p className="muted">None of your recognized skills appear in the market evidence for this role.</p>
        )}
      </article>
    </section>
  </>;
}
