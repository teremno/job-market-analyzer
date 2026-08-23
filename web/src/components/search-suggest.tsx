"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

export type Suggestion = {
  kind: "skill" | "role" | "source";
  code: string;
  label: string;
  postingCount: number;
};

/**
 * Free-text search box with taxonomy autocomplete. Typing suggests known
 * skills/roles (prefix matches first, then by posting count); picking one
 * applies the exact machine filter while PRESERVING the other active filters.
 */
export function SearchWithSuggestions({
  defaultValue,
  skills,
  roles,
  currentFilters,
}: {
  defaultValue: string;
  skills: Array<{ skill_code: string; skill_name: string; posting_count: number }>;
  roles: Array<{ role_code: string; role_name: string; posting_count: number }>;
  /** Active URL filters the suggestion navigation must preserve. */
  currentFilters: Record<string, string>;
}) {
  const router = useRouter();
  const [query, setQuery] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number | null>(null);
  const [prevDefault, setPrevDefault] = useState(defaultValue);

  // Keep the visible text in sync when filters change through soft
  // navigation (suggestion clicks, back/forward): this component is not
  // remounted, so defaultValue alone would go stale. React's recommended
  // adjust-state-during-render pattern avoids an effect here.
  if (prevDefault !== defaultValue) {
    setPrevDefault(defaultValue);
    setQuery(defaultValue);
    setOpen(false);
  }

  const pool: Suggestion[] = useMemo(
    () => [
      ...skills.map((s) => ({
        kind: "skill" as const,
        code: s.skill_code,
        label: s.skill_name,
        postingCount: s.posting_count,
      })),
      ...roles.map((r) => ({
        kind: "role" as const,
        code: r.role_code,
        label: r.role_name,
        postingCount: r.posting_count,
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
          a.score - b.score || b.item.postingCount - a.item.postingCount,
      )
      .slice(0, 8)
      .map(({ item }) => item);
  }, [query, pool]);

  const applyExactFilter = (item: Suggestion) => {
    setOpen(false);
    const paramKey = item.kind === "skill" ? "skill" : "role";
    // Preserve every other active filter from the current URL state.
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(currentFilters)) {
      if (key !== "q" && key !== item.kind && value) params.set(key, value);
    }
    params.set(paramKey, item.code);
    router.push(`/jobs?${params.toString()}`);
  };

  return (
    <label className="search-field suggest-root">
      <span>Title, skill or role</span>
      <input
        type="search"
        name="q"
        value={query}
        autoComplete="off"
        aria-label="Search postings by title, skill or role"
        maxLength={200}
        placeholder="e.g. Python — pick a suggestion or press Enter for title search"
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          if (closeTimer.current !== null) {
            window.clearTimeout(closeTimer.current);
            closeTimer.current = null;
          }
          setOpen(true);
        }}
        onBlur={() => {
          closeTimer.current = window.setTimeout(() => setOpen(false), 150);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      />
      {open && suggestions.length > 0 && (
        <ul className="suggest-list">
          {suggestions.map((item) => (
            <li key={`${item.kind}-${item.code}`}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyExactFilter(item)}
              >
                <span className={`suggest-kind suggest-kind-${item.kind}`}>
                  {item.kind === "skill" ? "Skill" : "Role"}
                </span>
                <strong>{item.label}</strong>
                <small>{item.postingCount} postings</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}

function rank(item: Suggestion, query: string): number {
  const label = item.label.toLowerCase();
  if (label === query) return 0;
  if (label.startsWith(query)) return 1;
  if (item.code.toLowerCase().startsWith(query)) return 2;
  if (label.includes(query)) return 3;
  return 99;
}
