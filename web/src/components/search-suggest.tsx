"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

export type Suggestion = {
  kind: "skill" | "role" | "source";
  code: string;
  label: string;
  hint: string;
};

const KIND_LABELS: Record<Suggestion["kind"], string> = {
  skill: "Skill",
  role: "Role",
  source: "Source",
};

function rank(item: Suggestion, query: string): number {
  const label = item.label.toLowerCase();
  if (label === query) return 0;
  if (label.startsWith(query)) return 1;
  if (item.code.toLowerCase().startsWith(query)) return 2;
  if (label.includes(query)) return 3;
  return 99;
}

/**
 * Free-text search box with taxonomy autocomplete. Typing suggests known
 * skills/roles/sources (prefix matches first); picking one applies the exact
 * machine filter instead of a loose text search.
 */
export function SearchWithSuggestions({
  defaultValue,
  skills,
  roles,
}: {
  defaultValue: string;
  skills: Array<{ skill_code: string; skill_name: string; posting_count: number }>;
  roles: Array<{ role_code: string; role_name: string; posting_count: number }>;
}) {
  const router = useRouter();
  const [query, setQuery] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const pool: Suggestion[] = useMemo(
    () => [
      ...skills.map((s) => ({
        kind: "skill" as const,
        code: s.skill_code,
        label: s.skill_name,
        hint: `${s.posting_count} postings`,
      })),
      ...roles.map((r) => ({
        kind: "role" as const,
        code: r.role_code,
        label: r.role_name,
        hint: `${r.posting_count} postings`,
      })),
    ],
    [skills, roles],
  );

  const suggestions = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (trimmed.length < 2) return [];
    return pool
      .map((item) => ({ item, score: rank(item, trimmed) }))
      .filter(({ score }) => score < 99)
      .sort(
        (a, b) =>
          a.score - b.score ||
          b.item.hint.localeCompare(a.item.hint, undefined, { numeric: true }),
      )
      .slice(0, 8)
      .map(({ item }) => item);
  }, [query, pool]);

  const applyExactFilter = (item: Suggestion) => {
    setOpen(false);
    if (item.kind === "skill") {
      router.push(`/jobs?skill=${encodeURIComponent(item.code)}`);
    } else if (item.kind === "role") {
      router.push(`/jobs?role=${encodeURIComponent(item.code)}`);
    } else {
      router.push(`/jobs?source=${encodeURIComponent(item.code)}`);
    }
  };

  return (
    <div className="search-field suggest-root" ref={containerRef}>
      <span>Title, skill or role</span>
      <input
        type="search"
        name="q"
        value={query}
        autoComplete="off"
        maxLength={200}
        placeholder="e.g. Python — pick a suggestion or press Enter for title search"
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      />
      {open && suggestions.length > 0 && (
        <ul className="suggest-list" role="listbox">
          {suggestions.map((item) => (
            <li key={`${item.kind}-${item.code}`}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyExactFilter(item)}
              >
                <span className={`suggest-kind suggest-kind-${item.kind}`}>
                  {KIND_LABELS[item.kind]}
                </span>
                <strong>{item.label}</strong>
                <small>{item.hint}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
