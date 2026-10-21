"use client";

import { AppShell } from "@/components/app-shell";
import { useDashboard } from "@/components/dashboard-provider";
import { DataState, EmptyState, PageHeader, Section } from "@/components/views";
import { generateMeetingBrief } from "@/lib/intelligence";
import { formatDate } from "@/lib/format";

/**
 * Meeting Brief — a briefing document, not another dashboard page.
 *
 * The promise: walk into your meeting prepared in under 60 seconds.
 */
export default function MeetingBriefPage() {
  const { tasks, referenceMs } = useDashboard();
  const brief = generateMeetingBrief(tasks, {
    meetingName: "Leadership meeting",
    referenceMs,
  });
  const summary = brief.summary;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Pre-read"
        title="Meeting Brief"
        subtitle="A briefing document for the meeting you are about to walk into."
      />

      <DataState>
        <div className="brief-doc">
          <Section
            title={brief.meeting_name}
            caption={`${summary.decisions_required} decisions · ${summary.critical_risk} critical risks · ${summary.blocked} blocked · ${summary.overdue} overdue`}
          >
            {brief.decisions.length > 0 ? (
              <>
                <div className="ep-group-label">Decisions</div>
                {brief.decisions.map((decision, index) => (
                  <div className="brief-item" key={decision.Task_ID}>
                    <span className="brief-num">{index + 1}</span>
                    <strong>{decision.Task}</strong>
                    <br />
                    <span className="dw-muted">
                      {[
                        decision.Department,
                        decision.Owner,
                        decision.Due_Date ? formatDate(decision.Due_Date) : "",
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </div>
                ))}
              </>
            ) : null}

            {brief.critical_risk.length > 0 ? (
              <>
                <div className="ep-group-label">Critical risks</div>
                {brief.critical_risk.map((risk, index) => (
                  <div className="brief-item" key={risk.Task_ID}>
                    <span className="brief-num">{index + 1}</span>
                    <strong>{risk.Task}</strong>
                    <br />
                    <span className="dw-muted">
                      {[risk.Department, risk.Owner].filter(Boolean).join(" · ")}
                    </span>
                  </div>
                ))}
              </>
            ) : null}

            {brief.friction_points.length > 0 ? (
              <>
                <div className="ep-group-label">Blocked</div>
                {brief.friction_points.slice(0, 5).map((point, index) => (
                  <div
                    className="brief-item"
                    key={`${point.blocker_owner}-${index}`}
                  >
                    <span className="brief-num">{index + 1}</span>
                    <strong>{point.blocker_owner}</strong> blocks{" "}
                    {point.blocked_count} items
                    <br />
                    <span className="dw-muted">{point.blocker_dept}</span>
                  </div>
                ))}
              </>
            ) : null}

            {brief.systemic_risks.length > 0 ? (
              <>
                <div className="ep-group-label">Questions to ask</div>
                {brief.systemic_risks.slice(0, 5).map((risk, index) => (
                  <div
                    className="brief-item"
                    key={`${risk.pattern_type}-${index}`}
                  >
                    <span className="brief-num">{index + 1}</span>
                    {risk.description}
                    <br />
                    <span className="dw-muted">{risk.recommendation}</span>
                  </div>
                ))}
              </>
            ) : null}

            {summary.total_open === 0 ? (
              <EmptyState>No open work to brief on.</EmptyState>
            ) : null}
          </Section>
        </div>
      </DataState>
    </AppShell>
  );
}
