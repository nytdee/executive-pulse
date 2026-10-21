"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";

interface ChangesPayload {
  changes: {
    new_overdue: Array<{ Task_ID: string; Task: string }>;
    newly_blocked: Array<{ Task_ID: string; Task: string }>;
    resolved: Array<{ Task_ID: string; Task: string }>;
    status_changes: Array<{
      Task_ID: string;
      Task: string;
      Old_Status: string;
      New_Status: string;
    }>;
    new_decisions: Array<{ Task_ID: string; Task: string }>;
  };
  total: number;
  hasBaseline: boolean;
  isFirstRun: boolean;
}

/**
 * Changes — what is different since the last review.
 */
export default function ChangesPage() {
  const { source, filters, persona, focus } = useDashboard();
  const [payload, setPayload] = useState<ChangesPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const params = new URLSearchParams();
    if (source.kind === "sheet" && source.sheetId) {
      params.set("source", "sheet");
      params.set("sheetId", source.sheetId);
      params.set("gid", source.gid || "0");
    }
    if (filters.departments.length) {
      params.set("department", filters.departments.join(","));
    }
    if (filters.owners.length) params.set("owner", filters.owners.join(","));
    if (filters.statuses.length) params.set("status", filters.statuses.join(","));
    if (filters.priorities.length) {
      params.set("priority", filters.priorities.join(","));
    }
    if (filters.search.trim()) params.set("search", filters.search.trim());
    if (filters.minScore > 0) params.set("minScore", String(filters.minScore));

    try {
      const response = await fetch(`/api/v1/changes?${params.toString()}`);
      const body = await response.json();
      if (!body.ok) {
        setError(body.error?.message ?? "Failed to load changes");
        return;
      }
      setPayload(body.data as ChangesPayload);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to load changes",
      );
    }
  }, [source, filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const changes = payload?.changes;
  const ordered: Array<{ label: string; text: string }> = [];

  for (const row of changes?.new_overdue ?? []) {
    ordered.push({ label: "New risk", text: row.Task });
  }
  for (const row of changes?.newly_blocked ?? []) {
    ordered.push({ label: "New blocker", text: row.Task });
  }
  for (const row of changes?.new_decisions ?? []) {
    ordered.push({ label: "Decision requested", text: row.Task });
  }
  for (const row of changes?.status_changes ?? []) {
    ordered.push({
      label: "Status change",
      text: `${row.Task}: ${row.Old_Status} → ${row.New_Status}`,
    });
  }
  for (const row of changes?.resolved ?? []) {
    ordered.push({ label: "Resolved", text: row.Task });
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Delta"
        title="Changes"
        subtitle="What is different since your last review."
      />

      {error ? (
        <div
          className="ep-empty"
          style={{ color: "var(--color-critical)", marginTop: "2rem" }}
        >
          {error}
        </div>
      ) : (
        <Section
          title="Meaningful changes"
          caption={
            payload?.hasBaseline
              ? `${ordered.length} changes since the last refresh.`
              : "No previous snapshot yet — changes appear after the next refresh."
          }
        >
          {ordered.length === 0 ? (
            <EmptyState>No new changes since your last review.</EmptyState>
          ) : (
            ordered.map((change, index) => (
              <div className="sig" key={`${change.text}-${index}`}>
                <span className="sig-bar" data-tone="navy" aria-hidden="true" />
                <div className="sig-main">
                  <div className="sig-title">{change.text}</div>
                  <div className="sig-signal">{change.label}</div>
                </div>
              </div>
            ))
          )}
        </Section>
      )}
    </AppShell>
  );
}
