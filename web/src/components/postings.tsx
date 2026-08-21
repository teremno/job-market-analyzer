import Link from "next/link";

import { formatDate, formatProvider, safeExternalUrl } from "@/lib/format";
import type { Posting } from "@/lib/types";

function Badges({ items, hrefBase }: { items: Array<{ code: string; name: string }>; hrefBase: "roles" | "skills" }) {
  const visible = items.slice(0, hrefBase === "skills" ? 5 : 3);
  return <div className="badges">
    {visible.map((item) => <Link key={item.code} href={`/${hrefBase}/${encodeURIComponent(item.code)}`} className="badge">{item.name}</Link>)}
    {items.length > visible.length && <span className="badge more">+{items.length - visible.length} more</span>}
    {items.length === 0 && <span className="muted">—</span>}
  </div>;
}

export function PostingsTable({ postings }: { postings: Posting[] }) {
  return (
    <div className="table-shell">
      <table>
        <thead><tr><th>Vacancy</th><th>Source / location</th><th>Roles</th><th>Skills mentioned</th><th>Published</th><th><span className="sr-only">Links</span></th></tr></thead>
        <tbody>
          {postings.map((posting) => {
            const sourceUrl = safeExternalUrl(posting.source_url);
            const applicationUrl = safeExternalUrl(posting.application_url);
            return <tr key={posting.job_posting_id}>
              <td><strong>{posting.title}</strong><span>{posting.company_name || "Company not provided"}</span></td>
              <td><span className="source-pill">{formatProvider(posting.source_provider)}</span><span>{posting.location || "Location not provided"}</span></td>
              <td><Badges items={posting.roles.map((r) => ({ code: r.role_code, name: r.role_name }))} hrefBase="roles" /></td>
              <td><Badges items={posting.skills.map((s) => ({ code: s.skill_code, name: s.skill_name }))} hrefBase="skills" /></td>
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
