import type { Metadata } from "next";

import { PostingsTable } from "@/components/postings";
import { BarList, DataError, EmptyState, MetricCard, PageHeader } from "@/components/ui";
import { getSkill, loadData } from "@/lib/api";

type Params = Promise<{ code: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  return { title: `Skill · ${(await params).code}` };
}

export default async function SkillPage({ params }: { params: Params }) {
  const { code } = await params;
  const result = await loadData(getSkill(code));
  if (!result.ok) return <><PageHeader eyebrow={`Skill / ${code}`} title="Skill detail">This skill could not be loaded.</PageHeader><DataError error={result.error} /></>;
  const skill = result.data;
  return <><PageHeader eyebrow={`Skill / ${skill.skill_code}`} title={skill.skill_name}>Direct mention evidence, associated roles and co-occurrence in source postings.</PageHeader><section className="metrics-grid compact"><MetricCard label="Source postings" value={skill.posting_count} note="Mentioning this skill" /></section><section className="insight-grid"><article className="panel"><div className="panel-heading"><h2>Associated roles</h2><span>Same postings</span></div><BarList kind="roles" items={skill.associated_roles.map((r) => ({ code: r.role_code, name: r.role_name, count: r.posting_count }))} /></article><article className="panel"><div className="panel-heading"><h2>Frequently co-mentioned skills</h2><span>No causal claim</span></div><BarList kind="skills" items={skill.co_occurring_skills.map((s) => ({ code: s.skill_code, name: s.skill_name, count: s.posting_count }))} /></article></section><section className="section-block"><div className="panel-heading"><h2>Representative postings</h2><span>Bounded API sample</span></div>{skill.representative_postings.length ? <PostingsTable postings={skill.representative_postings} /> : <EmptyState title="No current postings mention this skill.">The taxonomy code is valid, but this dataset has no matching current analysis.</EmptyState>}</section></>;
}
