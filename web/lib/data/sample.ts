/**
 * Executive Pulse — bundled sample dataset.
 *
 * Dates are relative to the current day so the demo never goes stale.
 * A dataset pinned to a fixed date turns every task overdue and stale
 * within weeks, which destroys the "signal over noise" premise.
 *
 * Regenerate with: python scripts/generate_sample_data.py
 */

import type { Task } from "@/lib/types";

interface SampleSpec {
  id: string;
  task: string;
  project: string;
  department: string;
  owner: string;
  ownerRole: string;
  status: Task["Status"];
  priority: Task["Priority"];
  /** Days from today. */
  start: number;
  due: number;
  completed?: number;
  impact: Task["Impact"];
  impactValue: number;
  blocker?: string;
  dependency?: string;
  blockerOwner?: string;
  /** Hours since the last update. */
  staleHours?: number;
  decision?: boolean;
  decisionBy?: number;
  decisionRequested?: string;
  sourceUrl?: string;
  notes: string;
}

const SPECS: SampleSpec[] = [
  {
    id: "T-001", task: "India market launch partner approval", project: "India Launch",
    department: "Strategy", owner: "Riya Sharma", ownerRole: "VP Partnerships",
    status: "Blocked", priority: "Critical", start: -18, due: -2,
    impact: "Critical", impactValue: 50000000,
    blocker: "Legal review pending for partnership agreement", blockerOwner: "Priya Legal",
    staleHours: 73, decision: true, decisionBy: 1,
    decisionRequested: "Approve escalation to Legal leadership to accelerate partner contract review",
    sourceUrl: "https://jira.company.com/browse/STRAT-142",
    notes: "Partner committed to a launch two days out. Legal review is 31 hours overdue. Rs 5Cr ARR at risk.",
  },
  {
    id: "T-002", task: "Enterprise contract pricing exception", project: "Enterprise Deal Q3",
    department: "Sales", owner: "Meera Singh", ownerRole: "Account Executive",
    status: "In Progress", priority: "High", start: -10, due: 0,
    impact: "Critical", impactValue: 25000000,
    blocker: "Pricing committee approval required", blockerOwner: "David CFO",
    staleHours: 1, decision: true, decisionBy: 0,
    decisionRequested: "Approve 15% discount exception for 3-year enterprise commitment",
    notes: "Rs 2.5Cr ARR. Pricing committee meets today. Competitor offering 12%.",
  },
  {
    id: "T-003", task: "Q4 marketing budget reallocation", project: "Marketing Planning",
    department: "Marketing", owner: "Aditi Patel", ownerRole: "CMO Office",
    status: "In Progress", priority: "High", start: -5, due: 4,
    impact: "High", impactValue: 8000000, staleHours: 25,
    decision: true, decisionBy: 4,
    decisionRequested: "Approve Rs 80L shift from events to digital based on ROI data",
    sourceUrl: "https://sheets.company.com/mkt-budget-q4",
    notes: "Events ROI negative. Digital channels showing 3.2x ROAS. Decision needed before Q4 execution.",
  },
  {
    id: "T-004", task: "Critical customer bug escalation", project: "Customer Retention",
    department: "Customer Success", owner: "Nikhil Gupta", ownerRole: "Senior CSM",
    status: "Blocked", priority: "Critical", start: -4, due: 1,
    impact: "Critical", impactValue: 12000000,
    blocker: "Engineering root cause analysis required", dependency: "T-006",
    blockerOwner: "Rajesh Eng", staleHours: 49, decision: true, decisionBy: 1,
    decisionRequested: "Authorize emergency hotfix sprint for enterprise customer Acme Corp",
    sourceUrl: "https://jira.company.com/browse/CS-892",
    notes: "Acme Corp threatening churn (Rs 1.2Cr ARR). Needs an eng call on hotfix versus full fix.",
  },
  {
    id: "T-005", task: "GDPR compliance audit", project: "Compliance",
    department: "Legal", owner: "Priya Legal", ownerRole: "General Counsel",
    status: "In Progress", priority: "Critical", start: -60, due: 9,
    impact: "Critical", impactValue: 750000, staleHours: 25,
    decision: true, decisionBy: 9,
    decisionRequested: "Approve budget for external audit firm (Rs 75K)",
    sourceUrl: "https://confluence.company.com/display/LEGAL/GDPR-Audit",
    notes: "Audit deadline in 9 days. Auditor availability confirmed. Budget approval needed.",
  },
  {
    id: "T-006", task: "Office lease renewal decision", project: "Facilities",
    department: "Operations", owner: "Sana Reddy", ownerRole: "Facilities Manager",
    status: "In Progress", priority: "High", start: -20, due: 12,
    impact: "High", impactValue: 5000000,
    blocker: "Board approval for 5-year term", staleHours: 25,
    decision: true, decisionBy: 12,
    decisionRequested: "Approve 5-year lease renewal at Rs 50L/yr versus exploring alternatives",
    sourceUrl: "https://drive.company.com/file/LEASE-2026",
    notes: "Current lease expires in a quarter. 60-day notice required. Market rates increased 18%.",
  },
  {
    id: "T-007", task: "Incident response plan update", project: "Security Operations",
    department: "Technology", owner: "Arjun Kumar", ownerRole: "Security Lead",
    status: "In Progress", priority: "Critical", start: -25, due: 6,
    impact: "Critical", impactValue: 0, staleHours: 2,
    decision: true, decisionBy: 6,
    decisionRequested: "Approve updated escalation matrix for SEV-1 incidents",
    sourceUrl: "https://confluence.company.com/display/SEC/IR-Plan",
    notes: "Board audit requirement. Legal review complete. Executive sign-off needed.",
  },
  {
    id: "T-008", task: "API v2 migration for marketing platform", project: "Platform Migration",
    department: "Technology", owner: "Arjun Kumar", ownerRole: "Engineering Lead",
    status: "Blocked", priority: "High", start: -60, due: 8,
    impact: "High", impactValue: 8000000,
    blocker: "QA sign-off pending", blockerOwner: "Meera QA", staleHours: 97,
    notes: "QA team capacity constrained. Migration blocks the marketing creative refresh (T-009).",
  },
  {
    id: "T-009", task: "Q3 performance creative refresh", project: "Brand Campaign",
    department: "Marketing", owner: "Aditi Patel", ownerRole: "Creative Director",
    status: "In Progress", priority: "High", start: -20, due: 7,
    impact: "High", impactValue: 12000000, dependency: "T-008", staleHours: 25,
    notes: "Waiting on API migration completion for dynamic creative assets. Campaign is live.",
  },
  {
    id: "T-010", task: "Salesforce CPQ implementation", project: "Sales Enablement",
    department: "Sales", owner: "Meera Singh", ownerRole: "Salesforce Admin",
    status: "Blocked", priority: "High", start: -45, due: 14,
    impact: "High", impactValue: 3000000,
    blocker: "Integration with billing system", staleHours: 73,
    notes: "Billing API changes delayed. Vendor ETA slipped. Project is at risk.",
  },
  {
    id: "T-011", task: "Product analytics migration", project: "Data Infrastructure",
    department: "Technology", owner: "Arjun Kumar", ownerRole: "Engineering Lead",
    status: "Blocked", priority: "High", start: -30, due: 10,
    impact: "High", impactValue: 1000000,
    blocker: "Data engineering capacity", dependency: "T-012",
    blockerOwner: "Meera Data", staleHours: 145,
    notes: "Blocks the customer health score model (T-012). Data team at capacity.",
  },
  {
    id: "T-012", task: "Customer health score model", project: "Customer Intelligence",
    department: "Customer Success", owner: "Nikhil Gupta", ownerRole: "CS Operations",
    status: "In Progress", priority: "High", start: -20, due: 11,
    impact: "High", impactValue: 0, dependency: "T-011", staleHours: 49,
    notes: "Model validation in progress. 3 pilot accounts. Launch targeted for the same week as T-011 completes.",
  },
  {
    id: "T-013", task: "Security vendor onboarding", project: "Vendor Management",
    department: "Operations", owner: "Sana Reddy", ownerRole: "Procurement Manager",
    status: "Overdue", priority: "Medium", start: -30, due: -1,
    impact: "Medium", impactValue: 1500000,
    blocker: "Security questionnaire incomplete", staleHours: 97,
    notes: "Vendor delayed SOC2 documentation. One day overdue. Legal reviewing fallback options.",
  },
  {
    id: "T-014", task: "International payroll setup", project: "Global Expansion",
    department: "People", owner: "Kabir Nair", ownerRole: "Global Mobility",
    status: "Blocked", priority: "Medium", start: -25, due: 5,
    impact: "Medium", impactValue: 2000000,
    blocker: "Local entity registration pending", staleHours: 73,
    notes: "UK entity registration delayed. Payroll vendor cannot proceed without the entity number.",
  },
  {
    id: "T-015", task: "Competitive intelligence report", project: "Market Strategy",
    department: "Strategy", owner: "Riya Sharma", ownerRole: "VP Partnerships",
    status: "Overdue", priority: "Medium", start: -15, due: -3,
    impact: "Medium", impactValue: 0, staleHours: 121,
    notes: "Report three days overdue. Analyst on leave. Delivery expected this week.",
  },
  {
    id: "T-016", task: "Q3 board financial package", project: "Board Reporting",
    department: "Finance", owner: "Vikram Joshi", ownerRole: "FP&A Director",
    status: "In Progress", priority: "High", start: -10, due: 5,
    impact: "High", impactValue: 0, staleHours: 3,
    notes: "Consolidating subsidiary financials. India entity revenue recognition pending on T-001.",
  },
  {
    id: "T-017", task: "Pricing strategy A/B test", project: "Pricing Optimization",
    department: "Product", owner: "Sonal Mehta", ownerRole: "Product Manager",
    status: "In Progress", priority: "High", start: -14, due: 9,
    impact: "High", impactValue: 3000000, staleHours: 0,
    notes: "Variant B showing +8% conversion. Needs an executive call on full rollout versus extended test.",
  },
  {
    id: "T-018", task: "Brand film final approval", project: "Brand Campaign",
    department: "Marketing", owner: "Dev Kapoor", ownerRole: "Brand Manager",
    status: "In Progress", priority: "Low", start: -12, due: 15,
    impact: "Low", impactValue: 500000, staleHours: 25,
    notes: "Final cut delivered. Minor colour grading feedback. On track for release.",
  },
  {
    id: "T-019", task: "Q4 engineering hiring plan", project: "Engineering Growth",
    department: "People", owner: "Kabir Nair", ownerRole: "Talent Acquisition Lead",
    status: "In Progress", priority: "Medium", start: -12, due: 20,
    impact: "Medium", impactValue: 4000000, staleHours: 25,
    notes: "12 roles to fill. 3 offers extended, 2 accepted. On track for plan finalisation.",
  },
  {
    id: "T-020", task: "Marketing attribution model", project: "Marketing Analytics",
    department: "Marketing", owner: "Aditi Patel", ownerRole: "Marketing Ops",
    status: "In Progress", priority: "High", start: -20, due: 13,
    impact: "High", impactValue: 2000000, staleHours: 25,
    notes: "Model recalibration in progress. Q3 data integration complete.",
  },
  {
    id: "T-021", task: "Employee engagement survey", project: "People Operations",
    department: "People", owner: "Kabir Nair", ownerRole: "People Ops Manager",
    status: "In Progress", priority: "Medium", start: -15, due: 18,
    impact: "Medium", impactValue: 0, staleHours: 2,
    notes: "Survey live. 65% participation so far. Target 80% by month end.",
  },
  {
    id: "T-022", task: "Customer advisory board planning", project: "Customer Engagement",
    department: "Customer Success", owner: "Nikhil Gupta", ownerRole: "VP Customer Success",
    status: "Not Started", priority: "Medium", start: 20, due: 35,
    impact: "Medium", impactValue: 1000000, staleHours: 49,
    notes: "Quarterly CAB scheduled. Agenda development starting shortly.",
  },
  {
    id: "T-023", task: "Partner portal redesign", project: "Partner Experience",
    department: "Product", owner: "Sonal Mehta", ownerRole: "Product Manager",
    status: "Not Started", priority: "Medium", start: 10, due: 45,
    impact: "Medium", impactValue: 5000000, staleHours: 73,
    notes: "Discovery phase. Dependent on India launch (T-001) partner requirements.",
  },
  {
    id: "T-024", task: "Annual planning kickoff", project: "Strategic Planning",
    department: "Finance", owner: "Vikram Joshi", ownerRole: "CFO Office",
    status: "Not Started", priority: "Critical", start: 12, due: 30,
    impact: "Critical", impactValue: 0, staleHours: 1,
    notes: "Executive offsite at the end of the month. Pre-read materials needed a fortnight before.",
  },
  {
    id: "T-025", task: "Series B data room preparation", project: "Fundraising",
    department: "Finance", owner: "Vikram Joshi", ownerRole: "FP&A Director",
    status: "In Progress", priority: "Critical", start: -20, due: 16,
    impact: "Critical", impactValue: 0, staleHours: 1,
    notes: "Investor due diligence starts soon. Financial models 80% complete. Dependent on T-016 board package.",
  },
  {
    id: "T-026", task: "AI feature prototype", project: "AI Initiative",
    department: "Product", owner: "Sonal Mehta", ownerRole: "Product Manager",
    status: "In Progress", priority: "High", start: -12, due: 21,
    impact: "High", impactValue: 10000000, staleHours: 2,
    notes: "Prototype demo ready in three weeks. Board preview requested. Compute cost Rs 1Cr.",
  },
  {
    id: "T-027", task: "Sales compensation plan revision", project: "Sales Operations",
    department: "Sales", owner: "Meera Singh", ownerRole: "Sales Ops Lead",
    status: "Not Started", priority: "High", start: 6, due: 25,
    impact: "High", impactValue: 0, staleHours: 49,
    notes: "Board compensation committee review scheduled. Final model needed before then.",
  },
  {
    id: "T-028", task: "Investor update deck", project: "Investor Relations",
    department: "Finance", owner: "Vikram Joshi", ownerRole: "CFO Office",
    status: "In Progress", priority: "Critical", start: -4, due: 3,
    impact: "Critical", impactValue: 0, staleHours: 2,
    notes: "Monthly update due shortly. Incorporating India launch (T-001) and enterprise deal (T-002) status.",
  },
  {
    id: "T-029", task: "Q2 performance review cycle", project: "Performance Management",
    department: "People", owner: "Kabir Nair", ownerRole: "People Ops Manager",
    status: "Done", priority: "Medium", start: -60, due: -20, completed: -21,
    impact: "Medium", impactValue: 0, staleHours: 505,
    notes: "Cycle closed. Calibration complete across all teams.",
  },
  {
    id: "T-030", task: "Brand identity refresh rollout", project: "Brand Campaign",
    department: "Marketing", owner: "Dev Kapoor", ownerRole: "Brand Manager",
    status: "Done", priority: "High", start: -45, due: -6, completed: -7,
    impact: "High", impactValue: 4000000, staleHours: 169,
    notes: "Rollout shipped across all touchpoints. Engagement up 11% week over week.",
  },
];

function isoDate(reference: Date, days: number): string {
  const date = new Date(
    Date.UTC(reference.getUTCFullYear(), reference.getUTCMonth(), reference.getUTCDate()),
  );
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function isoDateTime(reference: Date, hoursAgo: number): string {
  const date = new Date(reference.getTime() - hoursAgo * 3_600_000);
  return date.toISOString().slice(0, 16).replace("T", " ");
}

/** Build the sample dataset relative to `reference` (defaults to now). */
export function buildSampleTasks(reference: Date = new Date()): Task[] {
  return SPECS.map((spec) => ({
    Task_ID: spec.id,
    Task: spec.task,
    Project: spec.project,
    Department: spec.department,
    Owner: spec.owner,
    Owner_Role: spec.ownerRole,
    Status: spec.status,
    Priority: spec.priority,
    Start_Date: isoDate(reference, spec.start),
    Due_Date: isoDate(reference, spec.due),
    Completed_Date:
      spec.completed === undefined ? null : isoDate(reference, spec.completed),
    Impact: spec.impact,
    Impact_Value: spec.impactValue,
    Blocker: spec.blocker ?? "",
    Dependency: spec.dependency ?? "",
    Blocker_Owner: spec.blockerOwner ?? "",
    Last_Updated: isoDateTime(reference, spec.staleHours ?? 1),
    Executive_Decision_Required: spec.decision ?? false,
    Decision_By:
      spec.decisionBy === undefined ? null : isoDate(reference, spec.decisionBy),
    Decision_Requested: spec.decisionRequested ?? "",
    Source_URL: spec.sourceUrl ?? "",
    Notes: spec.notes,
  }));
}
