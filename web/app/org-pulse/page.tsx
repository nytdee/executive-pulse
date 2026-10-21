"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { getOrgPulseEnhanced } from "@/lib/intelligence";

/**
 * Org Pulse — a compact department view, not a wall of charts.
 */
export default function OrgPulsePage() {
  const { tasks } = useDashboard();
  const departments = getOrgPulseEnhanced(tasks);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Heat"
        title="Org Pulse"
        subtitle="Which part of the organization deserves attention."
      />

      <DataState>
        <Section
          title="Departments"
          caption="Ordered by risk. Risk is rate-based so departments can actually be compared."
        >
          {departments.length === 0 ? (
            <EmptyState>No department data.</EmptyState>
          ) : (
            <table className="ep-table">
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Open</th>
                  <th>At risk</th>
                  <th>Blocked</th>
                  <th>Critical</th>
                  <th>Stale</th>
                  <th>Decisions</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {departments.map((row) => (
                  <tr key={row.Department}>
                    <td>{row.Department}</td>
                    <td data-numeric="true">{row.Open}</td>
                    <td data-numeric="true">{row.At_Risk}</td>
                    <td data-numeric="true">{row.Blocked}</td>
                    <td data-numeric="true">{row.High_Impact}</td>
                    <td data-numeric="true">{row.Stale}</td>
                    <td data-numeric="true">{row.Decisions}</td>
                    <td data-numeric="true">
                      <span
                        className="chip"
                        data-tone={
                          row.Risk_Score >= 60
                            ? "critical"
                            : row.Risk_Score >= 30
                              ? "warning"
                              : "ok"
                        }
                      >
                        {row.Risk_Score}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      </DataState>
    </AppShell>
  );
}
