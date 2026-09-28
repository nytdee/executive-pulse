"""
Executive Pulse presentation layer.

SIGNAL-first rendering over the existing intelligence engine.
Business logic, scoring, ranking and filtering live in
app/engine and app/data — this module only decides what the
executive sees first and what sits behind an interaction.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from app.engine.intelligence import (
    detect_cross_team_friction,
    analyze_owner_load,
    detect_systemic_risks,
    generate_meeting_brief,
    get_executive_attention_queue,
    get_decision_queue_detailed,
    get_blocked_friction_detailed,
    get_org_pulse_enhanced,
)


# ---------------------------------------------------------------------------
# Small presentational helpers (no business logic)
# ---------------------------------------------------------------------------

def _fmt_money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return ""
    if pd.isna(amount) or amount <= 0:
        return ""
    if amount >= 1_000_000:
        text = f"{amount / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"${text}M"
    if amount >= 1_000:
        text = f"{amount / 1_000:.0f}"
        return f"${text}K"
    return f"${amount:,.0f}"


def _fmt_date(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        return pd.Timestamp(value).strftime("%b %-d")
    except ValueError:
        # Windows strftime has no %-d.
        return pd.Timestamp(value).strftime("%b %d").replace(" 0", " ")


def _fmt_date_full(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    try:
        return pd.Timestamp(value).strftime("%b %-d, %Y")
    except ValueError:
        return pd.Timestamp(value).strftime("%b %d, %Y").replace(" 0", " ")


def _due_text(row: pd.Series) -> str:
    due = row.get("Due_Date")
    try:
        if due is None or pd.isna(due):
            return ""
    except (TypeError, ValueError):
        return ""
    days = (pd.Timestamp(due).normalize() - pd.Timestamp.now().normalize()).days
    if days < 0:
        return f"{abs(days)}d overdue"
    if days == 0:
        return "Due today"
    if days == 1:
        return "Due tomorrow"
    return f"Due in {days}d"


def _days_since(value: Any) -> Optional[int]:
    try:
        if value is None or pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return max(0, (pd.Timestamp.now().normalize() - pd.Timestamp(value).normalize()).days)


def _impact_line(row: pd.Series) -> str:
    money = _fmt_money(row.get("Impact_Value"))
    if money:
        return f"{money} at risk"
    impact = str(row.get("Impact", "") or "").strip()
    if impact:
        return f"{impact} impact"
    return ""


def _primary_signal(row: pd.Series) -> Tuple[str, str]:
    """One short reason for the default view. Tone: critical / warning / navy / muted."""
    if bool(row.get("decision_required")):
        return ("Decision required", "navy")
    if bool(row.get("overdue")):
        return ("Overdue", "critical")
    if bool(row.get("blocked")):
        if str(row.get("Impact", "")) == "Critical":
            return ("Critical blocker", "critical")
        return ("Blocked", "warning")
    if bool(row.get("at_risk")):
        return ("At risk", "warning")
    if bool(row.get("dependency_risk")):
        return ("Dependency at risk", "warning")
    if bool(row.get("stale")):
        return ("No recent update", "muted")
    if bool(row.get("high_impact")):
        return ("High impact", "muted")
    return ("Watch", "muted")


def _signal_line(row: pd.Series) -> Tuple[str, str]:
    reason, tone = _primary_signal(row)
    due = _due_text(row)
    if due and due not in reason:
        return (f"{reason} · {due}", tone)
    return (reason, tone)


def _band_tone(score_band: str) -> str:
    return {
        "Critical": "critical",
        "High": "warning",
    }.get(str(score_band), "navy")


def _score_breakdown(row: pd.Series) -> List[Tuple[str, str]]:
    """Explain the attention score from engine flags. Mirrors engine weights."""
    parts: List[Tuple[str, str]] = []
    if bool(row.get("decision_required")):
        parts.append(("+5", "Executive decision required"))
    impact = str(row.get("Impact", ""))
    if impact == "Critical":
        parts.append(("+5", "Critical impact"))
    elif impact == "High":
        parts.append(("+3", "High impact"))
    if bool(row.get("blocked")):
        parts.append(("+4", "Blocked"))
    if bool(row.get("overdue")):
        parts.append(("+4", "Overdue"))
    if bool(row.get("at_risk")):
        parts.append(("+2", "Due within 48 hours"))
    if bool(row.get("stale")):
        parts.append(("+2", "No update in 48+ hours"))
    if bool(row.get("dependency_risk")):
        dep = str(row.get("Dependency", "") or "").strip()
        parts.append(("+2", f"Dependency at risk ({dep})" if dep else "Dependency at risk"))
    return parts


# ---------------------------------------------------------------------------
# Detail drawer (modal). Full context lives here, never on the main view.
# ---------------------------------------------------------------------------

def _render_detail_body(record: Dict[str, Any]) -> None:
    row = pd.Series(record)

    st.markdown(f"### {row.get('Task', 'Untitled')}")
    st.markdown(
        f"<div class='dw-muted'>{row.get('Department', '')} · {row.get('Project', '')}</div>",
        unsafe_allow_html=True,
    )

    # Why this matters
    st.markdown("<div class='dw-kicker'>Why this matters</div>", unsafe_allow_html=True)
    reasons = str(row.get("reason_codes", "") or "").strip()
    if reasons:
        for reason in [r.strip() for r in reasons.replace(";", ",").split(",") if r.strip()]:
            st.markdown(f"<div class='dw-body'>— {reason}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='dw-muted'>No active risk flags.</div>", unsafe_allow_html=True)

    # Score breakdown
    parts = _score_breakdown(row)
    if parts:
        st.markdown("<div class='dw-kicker'>Attention score</div>", unsafe_allow_html=True)
        rows_html = "".join(
            f"<div class='dw-score-row'><span>{label}</span><span>{points}</span></div>"
            for points, label in parts
        )
        total = row.get("attention_score", sum(int(p[1:]) for p, _ in parts))
        rows_html += f"<div class='dw-total'><span>Total</span><span>{total}</span></div>"
        st.markdown(rows_html, unsafe_allow_html=True)

    # Decision
    if bool(row.get("decision_required")):
        st.markdown("<div class='dw-kicker'>Decision required</div>", unsafe_allow_html=True)
        requested = str(row.get("Decision_Requested", "") or "").strip()
        st.markdown(
            f"<div class='dw-body'>{requested if requested else 'Executive input requested.'}</div>",
            unsafe_allow_html=True,
        )
        decision_by = _fmt_date_full(row.get("Decision_By"))
        if decision_by:
            st.markdown(f"<div class='dw-muted'>Decide by {decision_by}</div>", unsafe_allow_html=True)

    # Blocking
    blocker = str(row.get("Blocker", "") or "").strip()
    blocker_owner = str(row.get("Blocker_Owner", "") or "").strip()
    dependency = str(row.get("Dependency", "") or "").strip()
    if blocker or blocker_owner or dependency:
        st.markdown("<div class='dw-kicker'>What is blocking it</div>", unsafe_allow_html=True)
        if blocker:
            st.markdown(f"<div class='dw-body'>{blocker}</div>", unsafe_allow_html=True)
        if blocker_owner:
            st.markdown(f"<div class='dw-muted'>Blocker owner: {blocker_owner}</div>", unsafe_allow_html=True)
        if dependency:
            st.markdown(f"<div class='dw-muted'>Depends on: {dependency}</div>", unsafe_allow_html=True)

    # Impact / ownership / timing
    st.markdown("<div class='dw-kicker'>Impact</div>", unsafe_allow_html=True)
    impact_bits = [str(row.get("Impact", "") or "").strip()]
    money = _fmt_money(row.get("Impact_Value"))
    if money:
        impact_bits.append(money)
    st.markdown(f"<div class='dw-body'>{' · '.join(b for b in impact_bits if b)}</div>", unsafe_allow_html=True)

    st.markdown("<div class='dw-kicker'>Ownership and timing</div>", unsafe_allow_html=True)
    owner = str(row.get("Owner", "") or "").strip()
    role = str(row.get("Owner_Role", "") or "").strip()
    st.markdown(
        f"<div class='dw-body'>{owner}{f' · {role}' if role else ''}</div>",
        unsafe_allow_html=True,
    )
    due = _fmt_date_full(row.get("Due_Date"))
    due_extra = _due_text(row)
    if due:
        st.markdown(
            f"<div class='dw-muted'>Due {due}{f' ({due_extra})' if due_extra else ''} · "
            f"Status {row.get('Status', '')} · Priority {row.get('Priority', '')}</div>",
            unsafe_allow_html=True,
        )
    updated = row.get("Last_Updated")
    try:
        updated_text = pd.Timestamp(updated).strftime("%b %d, %Y %H:%M") if updated is not None and not pd.isna(updated) else ""
    except (TypeError, ValueError):
        updated_text = ""
    if updated_text:
        st.markdown(f"<div class='dw-muted'>Last updated {updated_text}</div>", unsafe_allow_html=True)

    notes = str(row.get("Notes", "") or "").strip()
    if notes:
        st.markdown("<div class='dw-kicker'>Notes</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='dw-body'>{notes}</div>", unsafe_allow_html=True)

    source = str(row.get("Source_URL", "") or "").strip()
    if source:
        st.markdown(f"[View source]({source})")


if hasattr(st, "dialog"):
    @st.dialog("Detail")
    def _open_detail(record: Dict[str, Any]) -> None:
        _render_detail_body(record)
else:  # pragma: no cover - very old Streamlit
    _open_detail = None  # type: ignore


def _review_button(record: Dict[str, Any], key: str, label: str = "Review") -> None:
    if _open_detail is not None:
        if st.button(label, key=key, type="secondary"):
            _open_detail(record)
    else:
        with st.expander(label):
            _render_detail_body(record)


# ---------------------------------------------------------------------------
# Compact signal row — the only default view for an item
# ---------------------------------------------------------------------------

def render_item_card(row: pd.Series, show_source: bool = True, compact: bool = False, _key_prefix: str = "gen") -> None:
    """Render one compact signal row. Full detail opens in a drawer."""
    record = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    task_id = str(record.get("Task_ID", "")) or str(record.get("Task", ""))[:12]
    signal, _ = _signal_line(row)
    tone = _band_tone(str(record.get("score_band", "")))
    impact = _impact_line(row)
    meta = " · ".join(p for p in [str(record.get("Department", "") or ""), str(record.get("Owner", "") or "")] if p)

    left, right = st.columns([11, 1.6])
    with left:
        st.markdown(
            f"<div class='sig'>"
            f"<span class='sig-bar tone-{tone}'></span>"
            f"<div class='sig-main'>"
            f"<div class='sig-title'>{record.get('Task', 'Untitled')}</div>"
            + (f"<div class='sig-meta'>{meta}</div>" if meta else "")
            + (f"<div class='sig-impact'>{impact}</div>" if impact else "")
            + f"<div class='sig-signal'><strong>{signal}</strong></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div class='sig-side'></div>", unsafe_allow_html=True)
        _review_button(record, key=f"rev-{_key_prefix}-{task_id}")


# ---------------------------------------------------------------------------
# Overview layers and module views
# ---------------------------------------------------------------------------

def render_attention_queue(df: pd.DataFrame, title: str = "Attention Required", max_items: int = 5) -> None:
    """Executive attention queue — Critical/High only, compact rows."""
    attention_df = get_executive_attention_queue(df, max_items=max_items, min_band="High")
    if attention_df.empty:
        st.info("Nothing requires executive attention right now.")
        return
    for _, row in attention_df.iterrows():
        render_item_card(row, _key_prefix="att")


def render_org_signal_compact(df: pd.DataFrame, max_rows: int = 5) -> None:
    """Very compact department friction summary for the overview."""
    org_df = get_org_pulse_enhanced(df)
    if org_df.empty:
        return
    shown = org_df.head(max_rows)
    for _, r in shown.iterrows():
        bits = []
        if int(r.get("High_Impact", 0)) > 0:
            bits.append(f"{int(r['High_Impact'])} critical")
        if int(r.get("Blocked", 0)) > 0:
            bits.append(f"{int(r['Blocked'])} blocked")
        if int(r.get("Decisions", 0)) > 0:
            bits.append(f"{int(r['Decisions'])} decision")
        open_count = int(r.get("Open", 0))
        at_risk = int(r.get("High_Impact", 0)) + int(r.get("Overdue", 0))
        if at_risk > 0 and f"{at_risk} at risk" not in bits:
            bits.append(f"{at_risk} at risk")
        st.markdown(
            f"<div class='sig'><div class='sig-main'>"
            f"<div class='sig-title'>{r['Department']}</div>"
            f"<div class='sig-signal'>{(' · '.join(bits)) if bits else f'{open_count} open'}</div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )


def render_decision_queue(df: pd.DataFrame) -> None:
    """Clean decision cards. Context lives behind Review."""
    decisions = get_decision_queue_detailed(df)
    if decisions.empty:
        st.info("No decisions waiting for executive input.")
        return
    st.markdown(
        f"<div class='grp-summary'>{len(decisions)} decisions waiting for executive input.</div>",
        unsafe_allow_html=True,
    )
    for _, row in decisions.iterrows():
        record = row.to_dict()
        task_id = str(record.get("Task_ID", ""))
        impact = _impact_line(row)
        due = _due_text(row)
        urgency = str(record.get("decision_urgency", "") or due).strip()
        left, right = st.columns([11, 1.6])
        with left:
            st.markdown(
                f"<div class='dec'>"
                f"<div class='dec-kicker'>Decision required</div>"
                f"<div class='dec-title'>{record.get('Task', 'Untitled')}</div>"
                f"<div class='dec-meta'>"
                + " · ".join(p for p in [
                    impact,
                    urgency,
                    str(record.get("Department", "") or ""),
                ] if p)
                + f"</div></div>",
                unsafe_allow_html=True,
            )
        with right:
            _review_button(record, key=f"rev-dec-{task_id}")


def render_at_risk(df: pd.DataFrame) -> None:
    """Exception view grouped by department."""
    risk_items = df[(df.get("at_risk", False) == True) | (df.get("high_impact", False) == True)]
    risk_items = risk_items[risk_items["Status"] != "Done"]
    if risk_items.empty:
        st.info("No material execution risks right now.")
        return
    risk_items = risk_items.sort_values(["attention_score", "Due_Date"], ascending=[False, True])
    st.markdown(
        f"<div class='grp-summary'>{len(risk_items)} issues could materially affect execution.</div>",
        unsafe_allow_html=True,
    )
    for dept in sorted(risk_items["Department"].unique()):
        dept_items = risk_items[risk_items["Department"] == dept]
        st.markdown(f"<div class='grp-label'>{dept}</div>", unsafe_allow_html=True)
        for _, row in dept_items.head(6).iterrows():
            render_item_card(row, _key_prefix=f"risk-{dept}")


def render_blocked_friction(df: pd.DataFrame) -> None:
    """Where the organization is stuck — grouped by blocker."""
    friction_data = get_blocked_friction_detailed(df)
    if friction_data["summary"]["total_blocked"] == 0:
        st.info("Nothing is blocked right now.")
        return

    st.markdown(
        f"<div class='grp-summary'>{friction_data['summary']['total_blocked']} items blocked "
        f"across {friction_data['summary']['departments_affected']} departments.</div>",
        unsafe_allow_html=True,
    )

    # Group by blocker description
    blocked = df[df.get("blocked", False) == True].copy()
    by_blocker: Dict[str, list] = {}
    for _, row in blocked.iterrows():
        key = (str(row.get("Blocker", "")) or "").strip() or "Unspecified blocker"
        by_blocker.setdefault(key, []).append(row)

    for blocker_name, rows in sorted(by_blocker.items(), key=lambda kv: -len(kv[1])):
        sub = pd.DataFrame(rows)
        depts = sorted(sub["Department"].unique())
        total_impact = pd.to_numeric(sub.get("Impact_Value", 0), errors="coerce").fillna(0).sum()
        oldest = 0
        for _, r in sub.iterrows():
            d = _days_since(r.get("Last_Updated"))
            if d is not None:
                oldest = max(oldest, d)
        summary_bits = [f"{len(sub)} items blocked", ", ".join(depts[:3])]
        if total_impact > 0:
            summary_bits.append(f"{_fmt_money(total_impact)} affected")
        if oldest > 0:
            summary_bits.append(f"oldest {oldest}d")
        st.markdown(f"<div class='grp-label'>{blocker_name}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='grp-summary'>{' · '.join(summary_bits)}</div>",
            unsafe_allow_html=True,
        )
        with st.expander(f"View {len(sub)} items"):
            for _, row in sub.sort_values("attention_score", ascending=False).iterrows():
                render_item_card(row, _key_prefix=f"blk-{blocker_name[:12]}")


def render_what_changed(changes: dict, limit: int = 5) -> None:
    """Meaningful changes only. Remainder behind an interaction."""
    if not changes or all(v.empty for v in changes.values()):
        st.info("No new changes since your last review.")
        return

    ordered: List[Tuple[str, pd.Series]] = []
    priority = [
        ("new_overdue", "New risk"),
        ("newly_blocked", "New blocker"),
        ("new_decisions", "Decision requested"),
        ("status_changes", "Status change"),
        ("resolved", "Resolved"),
    ]
    for key, label in priority:
        frame = changes.get(key)
        if frame is None or frame.empty:
            continue
        for _, row in frame.iterrows():
            ordered.append((label, row))

    if not ordered:
        st.info("No new changes since your last review.")
        return

    for label, row in ordered[:limit]:
        if isinstance(row, pd.Series) and "Old_Status" in row.index:
            text = f"{row.get('Task', '')}: {row.get('Old_Status', '')} → {row.get('New_Status', '')}"
        else:
            text = str(row.get("Task", "") if isinstance(row, pd.Series) else row)
        st.markdown(
            f"<div class='sig'><div class='sig-main'>"
            f"<div class='sig-title'>{text}</div>"
            f"<div class='sig-signal'>{label}</div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    if len(ordered) > limit:
        with st.expander(f"Show all {len(ordered)} changes"):
            for label, row in ordered[limit:]:
                if isinstance(row, pd.Series) and "Old_Status" in row.index:
                    text = f"{row.get('Task', '')}: {row.get('Old_Status', '')} → {row.get('New_Status', '')}"
                else:
                    text = str(row.get("Task", "") if isinstance(row, pd.Series) else row)
                st.markdown(
                    f"<div class='sig'><div class='sig-main'>"
                    f"<div class='sig-title'>{text}</div>"
                    f"<div class='sig-signal'>{label}</div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )


def render_org_pulse(org_df: pd.DataFrame) -> None:
    """Minimal department heat view. Compatible with both org-pulse schemas."""
    if org_df.empty:
        st.info("No department data.")
        return

    if "Risk_Score" not in org_df.columns:
        org_df = get_org_pulse_enhanced(org_df)

    # Dual-schema decisions column: enhanced uses Decisions, legacy uses Decision_Required.
    if "Decisions" in org_df.columns:
        decision_column = "Decisions"
    elif "Decision_Required" in org_df.columns:
        decision_column = "Decision_Required"
    else:
        decision_column = None

    risk_col = "High_Impact" if "High_Impact" in org_df.columns else ("High_Impact_Risk" if "High_Impact_Risk" in org_df.columns else None)

    table = pd.DataFrame({
        "Department": org_df["Department"],
        "Open": org_df["Open"] if "Open" in org_df.columns else 0,
        "Risk": org_df[risk_col] if risk_col else 0,
        "Blocked": org_df["Blocked"] if "Blocked" in org_df.columns else 0,
        "Decisions": org_df[decision_column] if decision_column else 0,
    })

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Department": st.column_config.TextColumn("Department"),
            "Open": st.column_config.NumberColumn("Open", format="%d"),
            "Risk": st.column_config.NumberColumn("Risk", format="%d"),
            "Blocked": st.column_config.NumberColumn("Blocked", format="%d"),
            "Decisions": st.column_config.NumberColumn("Decisions", format="%d"),
        },
    )
    st.markdown(
        "<div class='dw-muted'>Risk counts high-impact open work. Open a department in Detail View to investigate.</div>",
        unsafe_allow_html=True,
    )


def render_stale_work(df: pd.DataFrame) -> None:
    """Stale work grouped by department — counts first, items on demand."""
    stale = df[df.get("stale", False) == True].copy()
    if stale.empty:
        st.info("Everything is progressing. No stale work.")
        return
    stale = stale.sort_values(["attention_score", "Last_Updated"], ascending=[False, True])
    st.markdown(
        f"<div class='grp-summary'>{len(stale)} items have not materially progressed.</div>",
        unsafe_allow_html=True,
    )
    for dept in sorted(stale["Department"].unique()):
        dept_items = stale[stale["Department"] == dept]
        oldest = 0
        for _, r in dept_items.iterrows():
            d = _days_since(r.get("Last_Updated"))
            if d is not None:
                oldest = max(oldest, d)
        total_impact = pd.to_numeric(dept_items.get("Impact_Value", 0), errors="coerce").fillna(0).sum()
        bits = [f"{len(dept_items)} stale items"]
        if oldest > 0:
            bits.append(f"oldest {oldest}d")
        if total_impact > 0:
            bits.append(f"{_fmt_money(total_impact)} impact")
        st.markdown(f"<div class='grp-label'>{dept}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='grp-summary'>{' · '.join(bits)}</div>", unsafe_allow_html=True)
        with st.expander(f"View {len(dept_items)} items"):
            for _, row in dept_items.iterrows():
                render_item_card(row, _key_prefix=f"stale-{dept}")


def render_meeting_brief(df: pd.DataFrame, meeting_name: str = "") -> None:
    """Briefing-document style pre-read."""
    focus_depts = st.multiselect("Focus departments", sorted(df["Department"].unique()), key="brief-depts")
    focus_owners = st.multiselect("Focus owners", sorted(df["Owner"].unique()), key="brief-owners")

    if st.button("Generate brief", type="primary", key="brief-generate"):
        brief = generate_meeting_brief(
            df,
            meeting_name=meeting_name,
            meeting_date=datetime.now(),
            focus_departments=focus_depts if focus_depts else None,
            focus_owners=focus_owners if focus_owners else None,
        )
        s = brief["summary"]
        st.markdown("<div class='brief-doc'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='ep-eyebrow'>Executive brief</div>"
            f"<div class='ep-title'>{meeting_name or 'Meeting brief'}</div>"
            f"<div class='ep-subtitle'>{s['decisions_required']} decisions · {s['critical_risk']} critical risks · "
            f"{s['blocked']} blocked · {s['overdue']} overdue</div>",
            unsafe_allow_html=True,
        )

        if brief["decisions"]:
            st.markdown("<div class='grp-label'>Today's decisions</div>", unsafe_allow_html=True)
            for i, d in enumerate(brief["decisions"], 1):
                due = _fmt_date(d.get("Due_Date"))
                st.markdown(
                    f"<div class='brief-item'><span class='brief-num'>{i}</span>"
                    f"<strong>{d.get('Task', '')}</strong><br>"
                    f"<span class='dw-muted'>{d.get('Department', '')} · {d.get('Owner', '')}"
                    f"{f' · {due}' if due else ''}</span></div>",
                    unsafe_allow_html=True,
                )

        if brief["critical_risk"]:
            st.markdown("<div class='grp-label'>Critical risks</div>", unsafe_allow_html=True)
            for i, d in enumerate(brief["critical_risk"], 1):
                st.markdown(
                    f"<div class='brief-item'><span class='brief-num'>{i}</span>"
                    f"<strong>{d.get('Task', '')}</strong><br>"
                    f"<span class='dw-muted'>{d.get('Department', '')} · {d.get('Owner', '')}</span></div>",
                    unsafe_allow_html=True,
                )

        if brief["friction_points"]:
            st.markdown("<div class='grp-label'>Blocked items</div>", unsafe_allow_html=True)
            for i, fp in enumerate(brief["friction_points"][:5], 1):
                st.markdown(
                    f"<div class='brief-item'><span class='brief-num'>{i}</span>"
                    f"<strong>{fp['blocker_owner']}</strong> blocks {fp['blocked_count']} items"
                    f"<br><span class='dw-muted'>{fp['blocker_dept']}</span></div>",
                    unsafe_allow_html=True,
                )

        if brief["systemic_risks"]:
            st.markdown("<div class='grp-label'>Discussion points</div>", unsafe_allow_html=True)
            for i, sr in enumerate(brief["systemic_risks"][:5], 1):
                st.markdown(
                    f"<div class='brief-item'><span class='brief-num'>{i}</span>"
                    f"{sr['description']}<br>"
                    f"<span class='dw-muted'>{sr['recommendation']}</span></div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Filters — same behavior, compact presentation
# ---------------------------------------------------------------------------

def render_sidebar_filters(df: pd.DataFrame) -> dict:
    """Render sidebar filters and return filter values.

    Behavior identical to the foundation build: same widgets, same
    defaults, same return contract for apply_filters.
    """
    st.sidebar.header("Filters")

    departments = sorted(df["Department"].unique())
    selected_depts = st.sidebar.multiselect("Department", departments, default=departments, key="flt-dept")

    owners = sorted(df["Owner"].unique())
    selected_owners = st.sidebar.multiselect("Owner", owners, default=owners, key="flt-owner")

    statuses = sorted(df["Status"].unique())
    selected_statuses = st.sidebar.multiselect("Status", statuses, default=statuses, key="flt-status")

    priorities = sorted(df["Priority"].unique())
    selected_priorities = st.sidebar.multiselect("Priority", priorities, default=priorities, key="flt-priority")

    date_col = st.sidebar.selectbox("Date Field", ["Due_Date", "Start_Date", "Last_Updated"], key="flt-datecol")
    min_date = df[date_col].min()
    max_date = df[date_col].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date(),
            key="flt-daterange",
        )
    else:
        date_range = None

    search_query = st.sidebar.text_input("Search", placeholder="Task, project, owner, blocker...", key="flt-search")

    min_score = st.sidebar.slider("Min Attention Score", 0, 20, 0, key="flt-score")

    # Compact active-filter summary + reset (presentation only).
    active = 0
    if len(selected_depts) < len(departments):
        active += 1
    if len(selected_owners) < len(owners):
        active += 1
    if len(selected_statuses) < len(statuses):
        active += 1
    if len(selected_priorities) < len(priorities):
        active += 1
    if search_query:
        active += 1
    if min_score > 0:
        active += 1
    if date_range and len(date_range) == 2 and pd.notna(min_date) and pd.notna(max_date):
        if date_range[0] > min_date.date() or date_range[1] < max_date.date():
            active += 1

    if active > 0:
        st.sidebar.caption(f"Filters · {active} active")
        if st.sidebar.button("Reset filters", key="flt-reset", type="secondary"):
            for widget_key in ["flt-dept", "flt-owner", "flt-status", "flt-priority", "flt-datecol", "flt-daterange", "flt-search", "flt-score"]:
                st.session_state.pop(widget_key, None)
            st.rerun()

    return {
        "departments": selected_depts,
        "owners": selected_owners,
        "statuses": selected_statuses,
        "priorities": selected_priorities,
        "date_range": date_range,
        "date_col": date_col,
        "search": search_query,
        "min_score": min_score,
    }


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply all filters to dataframe. Unchanged from foundation."""
    from app.data.loader import (
        filter_by_departments, filter_by_owners, filter_by_status,
        filter_by_priority, filter_by_date_range, search_tasks
    )

    result = df.copy()

    if filters["departments"]:
        result = filter_by_departments(result, filters["departments"])
    if filters["owners"]:
        result = filter_by_owners(result, filters["owners"])
    if filters["statuses"]:
        result = filter_by_status(result, filters["statuses"])
    if filters["priorities"]:
        result = filter_by_priority(result, filters["priorities"])
    if filters["date_range"] and len(filters["date_range"]) == 2:
        result = filter_by_date_range(result, filters["date_range"][0], filters["date_range"][1], filters["date_col"])
    if filters["search"]:
        result = search_tasks(result, filters["search"])
    if filters["min_score"] > 0:
        result = result[result.get("attention_score", 0) >= filters["min_score"]]

    return result
