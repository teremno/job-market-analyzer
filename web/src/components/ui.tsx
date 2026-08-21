import Link from "next/link";
import type { ReactNode } from "react";

import { ApiClientError } from "@/lib/api";
import { formatNumber, percentage } from "@/lib/format";
import type { AnalysisCounts } from "@/lib/types";

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return (
    <header className="page-header">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{children}</p>
    </header>
  );
}

export function MetricCard({ label, value, note }: { label: string; value: string | number; note: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{typeof value === "number" ? formatNumber(value) : value}</strong>
      <small>{note}</small>
    </article>
  );
}

export function Coverage({ title, counts, zeroLabel }: { title: string; counts: AnalysisCounts; zeroLabel: string }) {
  const total = counts.analyzed_with_results + counts.analyzed_zero + counts.not_analyzed;
  const segments = [
    ["Analyzed with results", counts.analyzed_with_results, "coverage-good"],
    [zeroLabel, counts.analyzed_zero, "coverage-zero"],
    ["Not analyzed", counts.not_analyzed, "coverage-missing"],
  ] as const;
  return (
    <article className="panel coverage-panel">
      <div className="panel-heading"><h2>{title}</h2><span>{formatNumber(total)} postings</span></div>
      <div className="coverage-bar" aria-label={title}>
        {segments.map(([label, value, className]) => value > 0 && (
          <span key={label} className={className} style={{ width: `${percentage(value, total)}%` }} title={`${label}: ${value}`} />
        ))}
      </div>
      <dl className="coverage-legend">
        {segments.map(([label, value, className]) => (
          <div key={label}><dt><i className={className} />{label}</dt><dd>{formatNumber(value)} <small>{percentage(value, total)}%</small></dd></div>
        ))}
      </dl>
    </article>
  );
}

export function DataError({ error }: { error: unknown }) {
  const unavailable = error instanceof ApiClientError && error.kind === "unavailable";
  const notFound = error instanceof ApiClientError && error.kind === "not_found";
  return (
    <section className="state-card" role="alert">
      <span className="state-code">{notFound ? "404" : "OFFLINE"}</span>
      <h2>{notFound ? "This analytics view was not found." : unavailable ? "Backend unavailable." : "Data could not be loaded."}</h2>
      <p>{unavailable ? "Start the local read-only API, then refresh this page." : "Check that the API and dashboard use the same current contract."}</p>
      {unavailable && <code>job-market-analyzer serve --database .\job-market.sqlite3</code>}
      <Link href="/">Return to overview</Link>
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <section className="state-card"><span className="state-code">0 RESULTS</span><h2>{title}</h2><p>{children}</p></section>;
}

export function BarList({ items, kind }: { items: Array<{ code: string; name: string; count: number }>; kind: "roles" | "skills" }) {
  const max = Math.max(...items.map((item) => item.count), 1);
  if (items.length === 0) return <p className="muted">No analyzed results yet.</p>;
  return <ol className="bar-list">
    {items.map((item) => (
      <li key={item.code}>
        <Link href={`/${kind}/${encodeURIComponent(item.code)}`}>
          <span className="bar-label"><strong>{item.name}</strong><code>{item.code}</code></span>
          <span className="bar-track"><i style={{ width: `${(item.count / max) * 100}%` }} /></span>
          <b>{formatNumber(item.count)}</b>
        </Link>
      </li>
    ))}
  </ol>;
}
