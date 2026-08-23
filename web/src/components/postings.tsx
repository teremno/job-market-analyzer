import Link from "next/link";

import { formatDate, formatNumber, formatProvider, safeExternalUrl } from "@/lib/format";
import type { Posting } from "@/lib/types";

function Badges({ items, hrefBase }: { items: Array<{ code: string; name: string }>; hrefBase: "roles" | "skills" }) {
  const visible = items.slice(0, hrefBase === "skills" ? 5 : 3);
  return <div className="badges">
    {visible.map((item) => <Link key={item.code} href={`/${hrefBase}/${encodeURIComponent(item.code)}`} className="badge">{item.name}</Link>)}
    {items.length > visible.length && <span className="badge more">+{items.length - visible.length} more</span>}
    {items.length === 0 && <span className="muted">—</span>}
  </div>;
}

function formatSalary(posting: Posting): string | null {
  if (!posting.salary_annual_min && !posting.salary_annual_max) return null;
  const currency = posting.salary_currency ?? "";
  if (posting.salary_annual_min && posting.salary_annual_max) {
    const min = Number(posting.salary_annual_min);
    const max = Number(posting.salary_annual_max);
    if (Number.isFinite(min) && Number.isFinite(max)) {
      return `${currency} ${formatNumber(min)} – ${formatNumber(max)} / year`;
    }
  }
  const single = posting.salary_annual_min ?? posting.salary_annual_max;
  return single ? `${currency} ${formatNumber(Number(single))} / year` : null;
}

export function PostingsTable({ postings }: { postings: Posting[] }) {
  return (
    <div className="table-shell">
      <table>
        <thead><tr><th>Vacancy</th><th>Source / location</th><th>Roles</th><th>Skills mentioned</th><th>Signals</th><th>Published</th><th><span className="sr-only">Links</span></th></tr></thead>
        <tbody>
          {postings.map((posting) => {
            const sourceUrl = safeExternalUrl(posting.source_url);
            const applicationUrl = safeExternalUrl(posting.application_url);
            const salary = formatSalary(posting);
            return <tr key={posting.job_posting_id}>
              <td><strong>{posting.title}</strong><span>{posting.company_name || "Company not provided"}</span></td>
              <td><span className="source-pill">{formatProvider(posting.source_provider)}</span><span>{posting.location || "Location not provided"}</span></td>
              <td><Badges items={posting.roles.map((r) => ({ code: r.role_code, name: r.role_name }))} hrefBase="roles" /></td>
              <td><Badges items={posting.skills.map((s) => ({ code: s.skill_code, name: s.skill_name }))} hrefBase="skills" /></td>
              <td>
                <div className="badges">
                  {posting.seniority && <span className="badge">{posting.seniority.name}</span>}
                  {posting.arrangement && <span className="badge">{posting.arrangement.name}</span>}
                  {(posting.regions ?? []).slice(0, 2).map((region) => <span key={region.code} className="badge more">{region.name}</span>)}
                  {salary && <span>{salary}</span>}
                  {!posting.seniority && !posting.arrangement && !salary && <span className="muted">—</span>}
                </div>
              </td>
              <td>{formatDate(posting.published_at)}</td>
              <td><div className="row-links">
                {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer">View source<span className="sr-only"> for {posting.title}</span></a>}
                {applicationUrl && <a className="apply-link" href={applicationUrl} target="_blank" rel="noopener noreferrer">Apply<span className="sr-only"> for {posting.title}</span></a>}
              </div></td>
            </tr>
          })}
        </tbody>
      </table>
    </div>
  );
}
