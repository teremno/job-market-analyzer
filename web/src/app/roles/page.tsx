import type { Metadata } from "next";
import Link from "next/link";

import { DataError, PageHeader } from "@/components/ui";
import { getOverview, loadData } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { getRoleMeta, groupRolesByFamily } from "@/lib/roles-meta";

export const metadata: Metadata = { title: "Roles" };

export default async function RolesPage() {
  const result = await loadData(getOverview(100));
  if (!result.ok) return <><PageHeader eyebrow="Deterministic classification" title="Roles">Role analytics require the local API.</PageHeader><DataError error={result.error} /></>;
  const data = result.data;
  const countsByCode = new Map(data.top_roles.map((role) => [role.role_code, role]));
  const families = groupRolesByFamily(
    data.top_roles.map((role) => ({ code: role.role_code })),
  );

  return <>
    <PageHeader eyebrow="Deterministic classification" title="Roles">
      Every posting is classified into one of these job families. Pick a role to
      see how many postings mention it and which skills the market asks for.
    </PageHeader>
    {families.map(({ family, codes }) => (
      <section className="panel" key={family}>
        <div className="panel-heading"><h2>{family}</h2><span>{codes.length} roles</span></div>
        <ul>
          {codes.map((code) => {
            const meta = getRoleMeta(code);
            const count = countsByCode.get(code);
            return (
              <li key={code} style={{ marginBottom: "14px" }}>
                <Link href={`/roles/${encodeURIComponent(code)}`}>
                  <strong>{count?.role_name ?? code}</strong>
                </Link>
                {" "}
                <small className="muted">{formatNumber(count?.posting_count ?? 0)} postings</small>
                {meta && <p className="muted" style={{ margin: "4px 0 0" }}>{meta.description}</p>}
              </li>
            );
          })}
        </ul>
      </section>
    ))}
  </>;
}
