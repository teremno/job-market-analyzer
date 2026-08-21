import type { Metadata } from "next";

import { BarList, DataError, PageHeader } from "@/components/ui";
import { getOverview, loadData } from "@/lib/api";

export const metadata: Metadata = { title: "Skills" };

export default async function SkillsPage() {
  const result = await loadData(getOverview(100));
  if (!result.ok) return <><PageHeader eyebrow="Direct evidence" title="Skills">Skill analytics require the local API.</PageHeader><DataError error={result.error} /></>;
  const data = result.data;
  return <><PageHeader eyebrow="Direct evidence" title="Skills">Technologies and practices mentioned in postings by the current deterministic extractor.</PageHeader><section className="panel explorer-panel"><div className="panel-heading"><h2>Observed skills</h2><span>{data.top_skills.length} mentions</span></div><BarList kind="skills" items={data.top_skills.map((s) => ({ code: s.skill_code, name: s.skill_name, count: s.posting_count }))} /></section></>;
}
