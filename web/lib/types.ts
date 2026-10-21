/**
 * Executive Pulse — shared domain types.
 *
 * These mirror the Python reference engine (app/engine/*) exactly.
 * The parity test suite (tests/parity.test.ts) asserts the two
 * implementations produce identical output.
 */

export type ScoreBand = "Critical" | "High" | "Watch" | "Normal";

export type Status =
  | "Not Started"
  | "In Progress"
  | "Blocked"
  | "Done"
  | "On Hold"
  | "Overdue";

export type Priority = "Low" | "Medium" | "High" | "Critical";

export type Impact = "Low" | "Medium" | "High" | "Critical";

/** The canonical schema every data source is mapped onto. */
export interface Task {
  Task_ID: string;
  Task: string;
  Project: string;
  Department: string;
  Owner: string;
  Owner_Role: string;
  Status: Status;
  Priority: Priority;
  Start_Date: string | null;
  Due_Date: string | null;
  Completed_Date: string | null;
  Impact: Impact;
  Impact_Value: number;
  Blocker: string;
  Dependency: string;
  Blocker_Owner: string;
  Last_Updated: string | null;
  Executive_Decision_Required: boolean;
  Decision_By: string | null;
  Decision_Requested: string;
  Source_URL: string;
  Notes: string;
}

/** A task with engine flags, score and band attached. */
export interface ScoredTask extends Task {
  overdue: boolean;
  at_risk: boolean;
  blocked: boolean;
  stale: boolean;
  decision_required: boolean;
  dependency_risk: boolean;
  high_impact: boolean;
  reason_codes: string[];
  attention_score: number;
  score_band: ScoreBand;
}

export interface FrictionPoint {
  blocker_owner: string;
  blocker_dept: string;
  blocked_count: number;
  total_impact_value: number;
  max_days_blocked: number;
  severity: "Critical" | "High" | "Watch";
  blocked_tasks: Array<{
    task_id: string;
    task: string;
    dept: string;
    owner: string;
    impact: string;
    days_blocked: number;
    blocker: string;
  }>;
}

export interface OwnerLoad {
  owner: string;
  department: string;
  total_open: number;
  overdue: number;
  blocked: number;
  high_impact: number;
  decisions_required: number;
  avg_attention_score: number;
  load_level: "Overloaded" | "High" | "Normal" | "Light";
}

export interface SystemicRisk {
  pattern_type:
    | "recurring_blocker"
    | "owner_overload"
    | "dept_concentration"
    | "stale_cluster"
    | "dependency_chain";
  description: string;
  affected_items: string[];
  severity: "Critical" | "High" | "Watch";
  recommendation: string;
}

export interface OrgPulseRow {
  Department: string;
  Total: number;
  Open: number;
  Done: number;
  Completion_Rate: string;
  Avg_Days_to_Complete: number;
  Overdue: number;
  Overdue_Pct: string;
  Blocked: number;
  Blocked_Pct: string;
  At_Risk: number;
  High_Impact: number;
  Stale: number;
  Stale_Pct: string;
  Decisions: number;
  Avg_Attention_Score: number;
  Risk_Score: number;
}

export interface ChangeSet {
  new_overdue: ScoredTask[];
  newly_blocked: ScoredTask[];
  resolved: ScoredTask[];
  status_changes: Array<{
    Task_ID: string;
    Task: string;
    Old_Status: string;
    New_Status: string;
    Owner: string;
  }>;
  new_decisions: ScoredTask[];
}

export interface MeetingBrief {
  meeting_name: string;
  meeting_date: string;
  generated_at: string;
  summary: {
    total_open: number;
    decisions_required: number;
    critical_risk: number;
    high_risk: number;
    blocked: number;
    overdue: number;
    friction_points: number;
    systemic_risks: number;
    overloaded_owners: number;
  };
  decisions: ScoredTask[];
  critical_risk: ScoredTask[];
  high_risk: ScoredTask[];
  blocked: ScoredTask[];
  overdue: ScoredTask[];
  friction_points: FrictionPoint[];
  systemic_risks: SystemicRisk[];
  owner_loads: OwnerLoad[];
}

export interface Counts {
  total: number;
  open: number;
  attention: number;
  decisions: number;
  blocked: number;
  atRisk: number;
  stale: number;
  overdue: number;
  critical: number;
}
