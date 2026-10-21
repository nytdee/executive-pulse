"use client";

/**
 * Executive Pulse — filters and viewer controls.
 *
 * The persona lens and the freeform focus profile only *group* the
 * engine ranking. They never change a score.
 */

import { useMemo } from "react";

import { useDashboard, type Filters } from "@/components/dashboard-provider";
import { PERSONAS } from "@/lib/persona";

export function ControlsPanel() {
  const {
    tasks,
    filters,
    setFilters,
    resetFilters,
    persona,
    setPersona,
    focus,
    setFocus,
    focusKeywords,
  } = useDashboard();

  const departments = useMemo(
    () => Array.from(new Set(tasks.map((task) => task.Department))).sort(),
    [tasks],
  );
  const owners = useMemo(
    () => Array.from(new Set(tasks.map((task) => task.Owner))).sort(),
    [tasks],
  );
  const statuses = useMemo(
    () => Array.from(new Set(tasks.map((task) => task.Status))).sort(),
    [tasks],
  );
  const priorities = useMemo(
    () => Array.from(new Set(tasks.map((task) => task.Priority))).sort(),
    [tasks],
  );

  const activeCount =
    (filters.departments.length ? 1 : 0) +
    (filters.owners.length ? 1 : 0) +
    (filters.statuses.length ? 1 : 0) +
    (filters.priorities.length ? 1 : 0) +
    (filters.search ? 1 : 0) +
    (filters.minScore > 0 ? 1 : 0);

  const toggle = (key: keyof Filters, value: string) => {
    const current = filters[key] as unknown as string[];
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    setFilters({ [key]: next } as Partial<Filters>);
  };

  return (
    <div>
      <div className="ep-sidebar-label">Viewing as</div>
      <select
        className="ep-select"
        value={persona}
        onChange={(event) => setPersona(event.target.value)}
        aria-label="Viewing as"
      >
        {Object.keys(PERSONAS).map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>

      <div className="ep-sidebar-label">Your focus</div>
      <input
        className="ep-input"
        placeholder="brand launches, partnerships…"
        value={focus}
        onChange={(event) => setFocus(event.target.value)}
        aria-label="Your focus"
      />
      {focusKeywords.length > 0 ? (
        <div className="dw-muted" style={{ marginTop: "0.3rem", fontSize: "0.6875rem" }}>
          Focusing on: {focusKeywords.slice(0, 6).join(", ")}
          {focusKeywords.length > 6 ? "…" : ""}
        </div>
      ) : null}

      <div className="ep-sidebar-label">
        Filters{activeCount > 0 ? ` · ${activeCount}` : ""}
      </div>

      <FilterGroup
        label="Department"
        options={departments}
        selected={filters.departments}
        onToggle={(value) => toggle("departments", value)}
      />
      <FilterGroup
        label="Owner"
        options={owners}
        selected={filters.owners}
        onToggle={(value) => toggle("owners", value)}
      />
      <FilterGroup
        label="Status"
        options={statuses}
        selected={filters.statuses}
        onToggle={(value) => toggle("statuses", value)}
      />
      <FilterGroup
        label="Priority"
        options={priorities}
        selected={filters.priorities}
        onToggle={(value) => toggle("priorities", value)}
      />

      <label className="ep-label" htmlFor="search" style={{ marginTop: "0.8rem" }}>
        Search
      </label>
      <input
        id="search"
        className="ep-input"
        placeholder="Task, owner, blocker…"
        value={filters.search}
        onChange={(event) => setFilters({ search: event.target.value })}
      />

      <label
        className="ep-label"
        htmlFor="min-score"
        style={{ marginTop: "0.8rem" }}
      >
        Min attention score
      </label>
      <input
        id="min-score"
        type="range"
        min={0}
        max={20}
        value={filters.minScore}
        onChange={(event) => setFilters({ minScore: Number(event.target.value) })}
        style={{ width: "100%" }}
      />
      <div className="dw-muted" style={{ fontSize: "0.6875rem" }}>
        {filters.minScore}
      </div>

      {activeCount > 0 ? (
        <button
          type="button"
          className="ep-button"
          data-variant="quiet"
          style={{ width: "100%", marginTop: "0.7rem" }}
          onClick={resetFilters}
        >
          Reset filters
        </button>
      ) : null}
    </div>
  );
}

function FilterGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  if (options.length === 0) return null;
  return (
    <details className="ep-disclosure" style={{ marginBottom: "0.35rem" }}>
      <summary>
        {label}
        {selected.length > 0 ? ` · ${selected.length}` : ""}
      </summary>
      <div className="ep-disclosure-body" style={{ maxHeight: "11rem", overflowY: "auto" }}>
        {options.map((option) => (
          <label
            key={option}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.45rem",
              padding: "0.18rem 0",
              fontSize: "0.7813rem",
              color: "var(--color-ink-2)",
            }}
          >
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => onToggle(option)}
            />
            {option}
          </label>
        ))}
      </div>
    </details>
  );
}
