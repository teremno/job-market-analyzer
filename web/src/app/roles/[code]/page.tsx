import type { Metadata } from "next";

import { PostingsTable } from "@/components/postings";
import { BarList, DataError, EmptyState, MetricCard, PageHeader } from "@/components/ui";
import { getRole, loadData } from "@/lib/api";

type Params = Promise<{ code: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  return { title: `Role · ${(await params).code}` };
}

export default async function RolePage({ params }: { params: Params }) {
  const { code } = await params;
  const result = await loadData(getRole(code));
  if (!result.ok) return <><PageHeader eyebrow={`Role / ${code}`} title="Role detail">This role could not be loaded.</PageHeader><DataError error={result.error} /></>;
  const role = result.data;
  return <><PageHeader eyebrow={`Role / ${role.role_code}`} title={role.role_name}>Posting-level classification and direct skill mentions among matching vacancies.</PageHeader><section className="metrics-grid compact"><MetricCard label="Source postings" value={role.posting_count} note="Classified with this role" /></section><section className="panel"><div className="panel-heading"><h2>Skills mentioned in postings</h2><span>Not inferred requirements</span></div><BarList kind="skills" items={role.top_skills.map((s) => ({ code: s.skill_code, name: s.skill_name, count: s.posting_count }))} /></section><section className="section-block"><div className="panel-heading"><h2>Representative postings</h2><span>Bounded API sample</span></div>{role.representative_postings.length ? <PostingsTable postings={role.representative_postings} /> : <EmptyState title="No current postings for this role.">The taxonomy code is valid, but this dataset has no matching current analysis.</EmptyState>}</section></>;
}
