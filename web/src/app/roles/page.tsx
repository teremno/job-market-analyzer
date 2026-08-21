import type { Metadata } from "next";

import { BarList, DataError, PageHeader } from "@/components/ui";
import { getOverview, loadData } from "@/lib/api";

export const metadata: Metadata = { title: "Roles" };

export default async function RolesPage() {
  const result = await loadData(getOverview(100));
  if (!result.ok) return <><PageHeader eyebrow="Deterministic classification" title="Roles">Role analytics require the local API.</PageHeader><DataError error={result.error} /></>;
  const data = result.data;
  return <><PageHeader eyebrow="Deterministic classification" title="Roles">Observed role classifications across source postings with exact current analysis.</PageHeader><section className="panel explorer-panel"><div className="panel-heading"><h2>Observed roles</h2><span>{data.top_roles.length} classifications</span></div><BarList kind="roles" items={data.top_roles.map((r) => ({ code: r.role_code, name: r.role_name, count: r.posting_count }))} /></section></>;
}
