import type { Metadata } from "next";

import { Coverage, DataError, EmptyState, PageHeader } from "@/components/ui";
import { getSources, loadData } from "@/lib/api";
import { formatDate, formatNumber, formatProvider } from "@/lib/format";
import type { SourceSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Sources" };

function UpdateStatusNote({ source }: { source: SourceSummary }) {
  const status = source.last_update_status;
  if (!status || status === "completed") return null;
  if (status === "skipped") {
    return (
      <p className="update-status-note">
        Latest update skipped — source credentials are not configured on this
        deployment ({formatDate(source.last_update_finished_at ?? null)}).
      </p>
    );
  }
  return (
    <p className="update-status-warning">
      Last update attempt failed ({formatDate(source.last_update_finished_at ?? null)}). Data may be stale until the next successful run.
    </p>
  );
}

function SourceCard({ source }: { source: SourceSummary }) {
  return (
    <article className="source-card">
      <header>
        <div>
          <p className="eyebrow">Provider</p>
          <h2>{formatProvider(source.source_provider)}</h2>
          <code>{source.source_provider}</code>
        </div>
        <strong>{formatNumber(source.posting_count)}<small>source postings</small></strong>
      </header>
      <dl className="freshness">
        <div><dt>Newest published</dt><dd>{formatDate(source.newest_published_at)}</dd></div>
        <div><dt>Latest observed posting</dt><dd>{formatDate(source.newest_last_seen_at)}</dd></div>
        <div><dt>Last successful update</dt><dd>{formatDate(source.last_successful_update_at ?? null)}</dd></div>
      </dl>
      <UpdateStatusNote source={source} />
      <Coverage title="Role coverage" counts={source.role_analysis} zeroLabel="Analyzed Unknown" />
      <Coverage title="Skill coverage" counts={source.skill_analysis} zeroLabel="Analyzed zero" />
    </article>
  );
}

export default async function SourcesPage() {
  const result = await loadData(getSources());
  if (!result.ok) return <><PageHeader eyebrow="Dataset composition" title="Sources">Source summaries require the local API.</PageHeader><DataError error={result.error} /></>;
  const sources = result.data;
  return <>
    <PageHeader eyebrow="Dataset composition" title="Sources">
      Freshness and analysis coverage of postings currently persisted from each provider.
    </PageHeader>
    {sources.length === 0
      ? <EmptyState title="No sources in this dataset.">Collect postings into this database to populate source analytics.</EmptyState>
      : <div className="source-grid">{sources.map((source) => <SourceCard key={source.source_provider} source={source} />)}</div>}
  </>;
}
