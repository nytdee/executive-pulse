"""
Generate the Executive Pulse sample dataset relative to the current date.

The previous sample data was pinned to a fixed date (2026-09-28). Within
weeks every task was simultaneously overdue, stale and critical, which
destroyed the demo: the dashboard reported "everything is on fire" instead
of surfacing a handful of genuine signals.

This generator derives every date from `today`, so the dataset always shows
a realistic mix of overdue, at-risk, blocked, stale, healthy and completed
work. Run it to refresh the sample:

    python scripts/generate_sample_data.py

The output is deterministic for a given day, so the same fixture can be
regenerated and diffed.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
OUTPUT = os.path.join(REPO_ROOT, "app", "data", "sample_data.csv")

HEADER = [
    "Task_ID", "Task", "Project", "Department", "Owner", "Owner_Role", "Status",
    "Priority", "Start_Date", "Due_Date", "Completed_Date", "Impact", "Impact_Value",
    "Blocker", "Dependency", "Blocker_Owner", "Last_Updated",
    "Executive_Decision_Required", "Decision_By", "Decision_Requested",
    "Source_URL", "Notes",
]


def build_rows(today: datetime):
    """Return dataset rows with all dates relative to `today`."""
    d = lambda n: (today + timedelta(days=n)).strftime("%Y-%m-%d")
    ts = lambda days, hour: (today + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d %H:%M")

    return [
        # --- Executive decisions waiting (the decision queue must be non-empty) ---
        ["T-001", "India market launch partner approval", "India Launch", "Strategy", "Riya Sharma",
         "VP Partnerships", "Blocked", "Critical", d(-18), d(-2), "", "Critical", 50000000,
         "Legal review pending for partnership agreement", "", "Priya Legal", ts(-3, 9),
         "Yes", d(1), "Approve escalation to Legal leadership to accelerate partner contract review",
         "https://jira.company.com/browse/STRAT-142",
         "Partner committed to a launch two days out. Legal review is 31 hours overdue. Rs 5Cr ARR at risk."],

        ["T-002", "Enterprise contract pricing exception", "Enterprise Deal Q3", "Sales", "Meera Singh",
         "Account Executive", "In Progress", "High", d(-10), d(0), "", "Critical", 25000000,
         "Pricing committee approval required", "", "David CFO", ts(0, 9),
         "Yes", d(0), "Approve 15% discount exception for 3-year enterprise commitment", "",
         "Rs 2.5Cr ARR. Pricing committee meets today. Competitor offering 12%."],

        ["T-003", "Q4 marketing budget reallocation", "Marketing Planning", "Marketing", "Aditi Patel",
         "CMO Office", "In Progress", "High", d(-5), d(4), "", "High", 8000000,
         "", "", "", ts(-1, 15),
         "Yes", d(4), "Approve Rs 80L shift from events to digital based on ROI data",
         "https://sheets.company.com/mkt-budget-q4",
         "Events ROI negative. Digital channels showing 3.2x ROAS. Decision needed before Q4 execution."],

        ["T-004", "Critical customer bug escalation", "Customer Retention", "Customer Success", "Nikhil Gupta",
         "Senior CSM", "Blocked", "Critical", d(-4), d(1), "", "Critical", 12000000,
         "Engineering root cause analysis required", "T-006", "Rajesh Eng", ts(-2, 8),
         "Yes", d(1), "Authorize emergency hotfix sprint for enterprise customer Acme Corp",
         "https://jira.company.com/browse/CS-892",
         "Acme Corp threatening churn (Rs 1.2Cr ARR). Needs an eng call on hotfix versus full fix."],

        ["T-005", "GDPR compliance audit", "Compliance", "Legal", "Priya Legal",
         "General Counsel", "In Progress", "Critical", d(-60), d(9), "", "Critical", 750000,
         "", "", "", ts(-1, 10),
         "Yes", d(9), "Approve budget for external audit firm (Rs 75K)",
         "https://confluence.company.com/display/LEGAL/GDPR-Audit",
         "Audit deadline in 9 days. Auditor availability confirmed. Budget approval needed."],

        ["T-006", "Office lease renewal decision", "Facilities", "Operations", "Sana Reddy",
         "Facilities Manager", "In Progress", "High", d(-20), d(12), "", "High", 5000000,
         "Board approval for 5-year term", "", "", ts(-1, 13),
         "Yes", d(12), "Approve 5-year lease renewal at Rs 50L/yr versus exploring alternatives",
         "https://drive.company.com/file/LEASE-2026",
         "Current lease expires in a quarter. 60-day notice required. Market rates increased 18%."],

        ["T-007", "Incident response plan update", "Security Operations", "Technology", "Arjun Kumar",
         "Security Lead", "In Progress", "Critical", d(-25), d(6), "", "Critical", 0,
         "", "", "", ts(0, 8),
         "Yes", d(6), "Approve updated escalation matrix for SEV-1 incidents",
         "https://confluence.company.com/display/SEC/IR-Plan",
         "Board audit requirement. Legal review complete. Executive sign-off needed."],

        # --- Blocked, cross-team friction (the friction story) ---
        ["T-008", "API v2 migration for marketing platform", "Platform Migration", "Technology", "Arjun Kumar",
         "Engineering Lead", "Blocked", "High", d(-60), d(8), "", "High", 8000000,
         "QA sign-off pending", "", "Meera QA", ts(-4, 9),
         "No", "", "", "",
         "QA team capacity constrained. Migration blocks the marketing creative refresh (T-009)."],

        ["T-009", "Q3 performance creative refresh", "Brand Campaign", "Marketing", "Aditi Patel",
         "Creative Director", "In Progress", "High", d(-20), d(7), "", "High", 12000000,
         "", "T-008", "", ts(-1, 14),
         "No", "", "", "",
         "Waiting on API migration completion for dynamic creative assets. Campaign is live."],

        ["T-010", "Salesforce CPQ implementation", "Sales Enablement", "Sales", "Meera Singh",
         "Salesforce Admin", "Blocked", "High", d(-45), d(14), "", "High", 3000000,
         "Integration with billing system", "", "", ts(-3, 12),
         "No", "", "", "",
         "Billing API changes delayed. Vendor ETA slipped. Project is at risk."],

        ["T-011", "Product analytics migration", "Data Infrastructure", "Technology", "Arjun Kumar",
         "Engineering Lead", "Blocked", "High", d(-30), d(10), "", "High", 1000000,
         "Data engineering capacity", "T-012", "Meera Data", ts(-6, 14),
         "No", "", "", "",
         "Blocks the customer health score model (T-012). Data team at capacity."],

        ["T-012", "Customer health score model", "Customer Intelligence", "Customer Success", "Nikhil Gupta",
         "CS Operations", "In Progress", "High", d(-20), d(11), "", "High", 0,
         "", "T-011", "", ts(-2, 9),
         "No", "", "", "",
         "Model validation in progress. 3 pilot accounts. Launch targeted for the same week as T-011 completes."],

        ["T-013", "Security vendor onboarding", "Vendor Management", "Operations", "Sana Reddy",
         "Procurement Manager", "Overdue", "Medium", d(-30), d(-1), "", "Medium", 1500000,
         "Security questionnaire incomplete", "", "", ts(-4, 13),
         "No", "", "", "",
         "Vendor delayed SOC2 documentation. One day overdue. Legal reviewing fallback options."],

        ["T-014", "International payroll setup", "Global Expansion", "People", "Kabir Nair",
         "Global Mobility", "Blocked", "Medium", d(-25), d(5), "", "Medium", 2000000,
         "Local entity registration pending", "", "", ts(-3, 11),
         "No", "", "", "",
         "UK entity registration delayed. Payroll vendor cannot proceed without the entity number."],

        ["T-015", "Competitive intelligence report", "Market Strategy", "Strategy", "Riya Sharma",
         "VP Partnerships", "Overdue", "Medium", d(-15), d(-3), "", "Medium", 0,
         "", "", "", ts(-5, 17),
         "No", "", "", "",
         "Report three days overdue. Analyst on leave. Delivery expected this week."],

        # --- Healthy work (must exist, or the demo shows only crises) ---
        ["T-016", "Q3 board financial package", "Board Reporting", "Finance", "Vikram Joshi",
         "FP&A Director", "In Progress", "High", d(-10), d(5), "", "High", 0,
         "", "", "", ts(0, 7),
         "No", "", "", "",
         "Consolidating subsidiary financials. India entity revenue recognition pending on T-001."],

        ["T-017", "Pricing strategy A/B test", "Pricing Optimization", "Product", "Sonal Mehta",
         "Product Manager", "In Progress", "High", d(-14), d(9), "", "High", 3000000,
         "", "", "", ts(0, 12),
         "No", "", "", "",
         "Variant B showing +8% conversion. Needs an executive call on full rollout versus extended test."],

        ["T-018", "Brand film final approval", "Brand Campaign", "Marketing", "Dev Kapoor",
         "Brand Manager", "In Progress", "Low", d(-12), d(15), "", "Low", 500000,
         "", "", "", ts(-1, 10),
         "No", "", "", "",
         "Final cut delivered. Minor colour grading feedback. On track for release."],

        ["T-019", "Q4 engineering hiring plan", "Engineering Growth", "People", "Kabir Nair",
         "Talent Acquisition Lead", "In Progress", "Medium", d(-12), d(20), "", "Medium", 4000000,
         "", "", "", ts(-1, 16),
         "No", "", "", "",
         "12 roles to fill. 3 offers extended, 2 accepted. On track for plan finalisation."],

        ["T-020", "Marketing attribution model", "Marketing Analytics", "Marketing", "Aditi Patel",
         "Marketing Ops", "In Progress", "High", d(-20), d(13), "", "High", 2000000,
         "", "", "", ts(-1, 15),
         "No", "", "", "",
         "Model recalibration in progress. Q3 data integration complete."],

        ["T-021", "Employee engagement survey", "People Operations", "People", "Kabir Nair",
         "People Ops Manager", "In Progress", "Medium", d(-15), d(18), "", "Medium", 0,
         "", "", "", ts(0, 11),
         "No", "", "", "",
         "Survey live. 65% participation so far. Target 80% by month end."],

        ["T-022", "Customer advisory board planning", "Customer Engagement", "Customer Success", "Nikhil Gupta",
         "VP Customer Success", "Not Started", "Medium", d(20), d(35), "", "Medium", 1000000,
         "", "", "", ts(-2, 14),
         "No", "", "", "",
         "Quarterly CAB scheduled. Agenda development starting shortly."],

        ["T-023", "Partner portal redesign", "Partner Experience", "Product", "Sonal Mehta",
         "Product Manager", "Not Started", "Medium", d(10), d(45), "", "Medium", 5000000,
         "", "", "", ts(-3, 10),
         "No", "", "", "",
         "Discovery phase. Dependent on India launch (T-001) partner requirements."],

        ["T-024", "Annual planning kickoff", "Strategic Planning", "Finance", "Vikram Joshi",
         "CFO Office", "Not Started", "Critical", d(12), d(30), "", "Critical", 0,
         "", "", "", ts(0, 9),
         "No", "", "", "",
         "Executive offsite at the end of the month. Pre-read materials needed a fortnight before."],

        ["T-025", "Series B data room preparation", "Fundraising", "Finance", "Vikram Joshi",
         "FP&A Director", "In Progress", "Critical", d(-20), d(16), "", "Critical", 0,
         "", "", "", ts(0, 14),
         "No", "", "", "",
         "Investor due diligence starts soon. Financial models 80% complete. Dependent on T-016 board package."],

        ["T-026", "AI feature prototype", "AI Initiative", "Product", "Sonal Mehta",
         "Product Manager", "In Progress", "High", d(-12), d(21), "", "High", 10000000,
         "", "", "", ts(0, 10),
         "No", "", "", "",
         "Prototype demo ready in three weeks. Board preview requested. Compute cost Rs 1Cr."],

        ["T-027", "Sales compensation plan revision", "Sales Operations", "Sales", "Meera Singh",
         "Sales Ops Lead", "Not Started", "High", d(6), d(25), "", "High", 0,
         "", "", "", ts(-2, 11),
         "No", "", "", "",
         "Board compensation committee review scheduled. Final model needed before then."],

        ["T-028", "Investor update deck", "Investor Relations", "Finance", "Vikram Joshi",
         "CFO Office", "In Progress", "Critical", d(-4), d(3), "", "Critical", 0,
         "", "", "", ts(0, 15),
         "No", "", "", "",
         "Monthly update due shortly. Incorporating India launch (T-001) and enterprise deal (T-002) status."],

        # --- Completed work (so completion rate and "resolved" deltas are real) ---
        ["T-029", "Q2 performance review cycle", "Performance Management", "People", "Kabir Nair",
         "People Ops Manager", "Done", "Medium", d(-60), d(-20), d(-21), "Medium", 0,
         "", "", "", ts(-21, 17),
         "No", "", "", "",
         "Cycle closed. Calibration complete across all teams."],

        ["T-030", "Brand identity refresh rollout", "Brand Campaign", "Marketing", "Dev Kapoor",
         "Brand Manager", "Done", "High", d(-45), d(-6), d(-7), "High", 4000000,
         "", "", "", ts(-7, 12),
         "No", "", "", "",
         "Rollout shipped across all touchpoints. Engagement up 11% week over week."],
    ]


def main() -> None:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = build_rows(today)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    # newline="" with the csv module lets it emit "\r\n" as the CSV
    # standard requires, but the lineterminator is pinned so the file is
    # byte-identical on every platform.
    with open(OUTPUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT}")
    print(f"Reference date: {today.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()
