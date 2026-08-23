import type { Metadata } from "next";
import Link from "next/link";

import { PostingsTable } from "@/components/postings";
import { BarList, DataError, EmptyState, MetricCard, PageHeader } from "@/components/ui";
import { getRole, loadData } from "@/lib/api";
import { formatPercentage } from "@/lib/format";
import { getRoleMeta } from "@/lib/roles-meta";

type Params = Promise<{ code: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  return { title: `Role · ${(await params).code}` };
}

export default async function RolePage({ params }: { params: Params }) {
  const { code } = await params;
  const result = await loadData(getRole(code));
  if (!result.ok) return <><PageHeader eyebrow={`Role / ${code}`} title="Role detail">This role could not be loaded.</PageHeader><DataError error={result.error} /></>;
  const role = result.data;
  const meta = getRoleMeta(role.role_code);
  const topSkills = role.top_skills.slice(0, 12);

  return <>
    <PageHeader eyebrow={`Role / ${role.role_code}`} title={role.role_name}>
      {meta?.description ?? "Posting-level classification and direct skill mentions among matching vacancies."}
    </PageHeader>

    <section className="metrics-grid compact">
      <MetricCard label="Source postings" value={role.posting_count} note="Classified with this role" />
    </section>

    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">What the market asks for</p>
          <h2>Most-mentioned skills for {role.role_name}</h2>
        </div>
        <Link className="apply-link" href={`/gap?role=${encodeURIComponent(role.role_code)}`}>
          Check my gap for this role →
        </Link>
      </div>
      <p className="muted">
        Share shows in how many of this role&apos;s postings each skill is
        mentioned. Mentioned is not the same as required.
      </p>
      {topSkills.length ? (
        <BarList kind="skills" items={topSkills.map((skill) => ({
          code: skill.skill_code,
          name: `${skill.skill_name} · ${formatPercentage(
            role.posting_count > 0 ? skill.posting_count / role.posting_count : 0,
          )}`,
          count: skill.posting_count,
        }))} />
      ) : (
        <p className="muted">No skill mentions recorded for this role yet.</p>
      )}
    </section>

    <section className="section-block">
      <div className="panel-heading"><h2>Representative postings</h2><span>Bounded API sample</span></div>
      {role.representative_postings.length ? <PostingsTable postings={role.representative_postings} /> : <EmptyState title="No current postings for this role.">The taxonomy code is valid, but this dataset has no matching current analysis.</EmptyState>}
    </section>
  </>;
}
