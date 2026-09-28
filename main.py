"""
Executive Pulse - Main Streamlit Application.
A decision-first operating layer for time-constrained executives.

Presentation layer only. Data loading, rule engine, attention scoring,
ranking and filtering live in app/data, app/engine and app/components.
"""

import json
import os

import pandas as pd
import streamlit as st

# Local imports — business logic preserved as-is.
from app.components.theme import THEME_OPTIONS, apply_theme
from app.components.ui import (
    render_attention_queue,
    render_decision_queue,
    render_at_risk,
    render_blocked_friction,
    render_what_changed,
    render_org_pulse,
    render_org_signal_compact,
    render_stale_work,
    render_meeting_brief,
    render_sidebar_filters,
    apply_filters,
)
from app.data.loader import load_and_validate, get_data_freshness
from app.engine.intelligence import get_org_pulse_enhanced
from app.engine.rule_engine import (
    compute_all_flags,
    rank_attention,
    get_attention_queue,
    get_decision_queue,
    compute_changes,
)


# ---------------------------------------------------------------------------
# Page configuration (no decorative icon)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Executive Pulse",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


# ---------------------------------------------------------------------------
# Data layer — unchanged processing pipeline
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_data(source_type: str, source_path: str = None, uploaded_file=None, sheet_id: str = None, gid: str = "0") -> pd.DataFrame:
    """Load and process data with caching."""
    if source_type == "csv" and source_path:
        df = load_and_validate(file_path=source_path)
    elif source_type == "upload" and uploaded_file:
        df = load_and_validate(uploaded_file=uploaded_file)
    elif source_type == "gsheet" and sheet_id:
        df = load_and_validate(sheet_id=sheet_id, gid=gid)
    else:
        # Default to sample data
        default_path = os.path.join(os.path.dirname(__file__), "app", "data", "sample_data.csv")
        df = load_and_validate(file_path=default_path)

    # Compute flags and scores
    df = compute_all_flags(df)
    df = rank_attention(df)
    return df


SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "app", "data", ".snapshot.json")
SNAPSHOT_COLUMNS = [
    "Task_ID", "Task", "Project", "Department", "Owner", "Status",
    "Due_Date", "Last_Updated", "Executive_Decision_Required", "Blocker",
    "overdue", "blocked", "decision_required",
]


def _load_snapshot() -> pd.DataFrame | None:
    """Load the previous dataset snapshot for change detection."""
    try:
        if not os.path.exists(SNAPSHOT_PATH):
            return None
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as handle:
            records = json.load(handle)
        if not records:
            return None
        previous = pd.DataFrame(records)
        for column in ("Due_Date", "Last_Updated"):
            if column in previous.columns:
                previous[column] = pd.to_datetime(previous[column], errors="coerce")
        for column in ("overdue", "blocked", "decision_required"):
            if column in previous.columns:
                previous[column] = previous[column].astype(bool)
        return previous
    except (OSError, ValueError):
        return None


def _save_snapshot(df: pd.DataFrame) -> None:
    """Persist the current dataset for the next review."""
    try:
        available = [c for c in SNAPSHOT_COLUMNS if c in df.columns]
        snapshot = df[available].copy()
        for column in ("Due_Date", "Last_Updated"):
            if column in snapshot.columns:
                snapshot[column] = pd.to_datetime(snapshot[column], errors="coerce").astype(str)
        for column in ("Executive_Decision_Required",):
            if column in snapshot.columns:
                snapshot[column] = snapshot[column].astype(str)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as handle:
            json.dump(snapshot.to_dict("records"), handle)
    except (OSError, ValueError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Presentation helpers (engine output only, no logic changes)
# ---------------------------------------------------------------------------

def _safe_len(value) -> int:
    """Return a stable length for Series/DataFrames/lists."""
    try:
        return len(value)
    except TypeError:
        return 0


def _metric_counts(df: pd.DataFrame) -> dict:
    """Build display counts using the existing engine functions."""
    total_open = len(df[df["Status"] != "Done"])
    attention = get_attention_queue(df)
    decisions = get_decision_queue(df)
    blocked = df[df.get("blocked", False) == True]
    at_risk = df[
        (df.get("at_risk", False) == True)
        | (df.get("high_impact", False) == True)
    ]
    at_risk = at_risk[at_risk["Status"] != "Done"]

    critical = 0
    if "score_band" in df.columns:
        critical = int((df["score_band"] == "Critical").sum())

    return {
        "open": total_open,
        "attention": _safe_len(attention),
        "decisions": _safe_len(decisions),
        "blocked": _safe_len(blocked),
        "at_risk": _safe_len(at_risk),
        "critical": critical,
    }


def render_executive_header(df: pd.DataFrame, freshness: str) -> None:
    """Calm executive state: what needs attention, in one glance."""
    counts = _metric_counts(df)
    # Portable day format (Windows strftime has no %-d).
    from datetime import datetime
    today = datetime.now().strftime("%A, %B %d").replace(" 0", " ")

    st.markdown('<div class="ep-eyebrow">Executive operating layer</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Executive Pulse</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='ep-state-line'><strong>{today}</strong> · "
        f"{counts['attention']} things require your attention.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='ep-freshness'>{counts['decisions']} decisions waiting · "
        f"{counts['critical']} critical risks · {counts['blocked']} blocked items<br>"
        f"Data refreshed: {freshness} · {len(df)} total items</div>",
        unsafe_allow_html=True,
    )


def _section(title: str, caption: str = "") -> None:
    st.markdown(
        f"<div class='ep-section'><div class='ep-section-title'>{title}</div>"
        + (f"<div class='ep-section-caption'>{caption}</div>" if caption else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def render_detail_page(df: pd.DataFrame, filters: dict) -> None:
    """Existing operational detail data in a restrained table."""
    st.markdown('<div class="ep-eyebrow">Operational detail</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">All Items</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">The complete operational dataset, available when deeper investigation is required.</div>',
        unsafe_allow_html=True,
    )

    filtered = apply_filters(df, filters)

    st.markdown(
        f"<div class='ep-freshness'>Showing {len(filtered)} of {len(df)} items</div>",
        unsafe_allow_html=True,
    )

    display_cols = [
        "Task_ID", "Task", "Project", "Department", "Owner", "Status",
        "Priority", "Due_Date", "Impact", "Blocker", "Dependency",
        "attention_score", "score_band", "reason_codes",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]

    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Due_Date": st.column_config.DateColumn("Due Date", format="YYYY-MM-DD"),
            "attention_score": st.column_config.NumberColumn("Score", format="%d"),
            "score_band": st.column_config.TextColumn("Band"),
        },
    )


# ---------------------------------------------------------------------------
# Pages — four-layer overview plus focused exception views
# ---------------------------------------------------------------------------

def render_overview_page(df: pd.DataFrame, changes: dict, prev_df: pd.DataFrame = None) -> None:
    """Overview: state, what needs me, organization, what changed."""
    render_executive_header(df, get_data_freshness(df))

    _section("What needs your attention", "The highest-priority exceptions surfaced by the decision engine.")
    render_attention_queue(df, "What needs your attention", max_items=5)

    _section("Organization", "Where the organization is experiencing friction.")
    render_org_signal_compact(df, max_rows=5)

    _section("What changed", "Meaningful changes since your last review.")
    render_what_changed(changes, limit=5)


def render_attention_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Signal</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Attention</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">Only items the decision engine considers worth executive time.</div>',
        unsafe_allow_html=True,
    )
    render_attention_queue(df, "Attention", max_items=7)


def render_decisions_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Input required</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Decisions</div>', unsafe_allow_html=True)
    render_decision_queue(df)


def render_risk_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Exceptions</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">At Risk</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">Where execution could miss, why, and what it affects.</div>',
        unsafe_allow_html=True,
    )
    render_at_risk(df)


def render_blocked_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Friction</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Blocked</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">Where the organization is stuck, grouped by blocker.</div>',
        unsafe_allow_html=True,
    )
    render_blocked_friction(df)


def render_changes_page(changes: dict) -> None:
    st.markdown('<div class="ep-eyebrow">Delta</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Changes</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">What is different since your last review.</div>',
        unsafe_allow_html=True,
    )
    render_what_changed(changes, limit=10)


def render_org_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Heat</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Org Pulse</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">Which part of the organization deserves attention.</div>',
        unsafe_allow_html=True,
    )
    render_org_pulse(get_org_pulse_enhanced(df))


def render_stale_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Drift</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Stale Work</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">Work that has not materially progressed.</div>',
        unsafe_allow_html=True,
    )
    render_stale_work(df)


def render_brief_page(df: pd.DataFrame) -> None:
    st.markdown('<div class="ep-eyebrow">Pre-read</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Meeting Brief</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">A briefing document for the meeting you are about to walk into.</div>',
        unsafe_allow_html=True,
    )
    meeting_name = st.text_input("Meeting name", placeholder="Q3 Board Review")
    render_meeting_brief(df, meeting_name)


PAGES = [
    "Overview",
    "Attention",
    "Decisions",
    "At Risk",
    "Blocked",
    "Changes",
    "Org Pulse",
    "Stale Work",
    "Meeting Brief",
    "Detail View",
]


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

def main():
    """Main application entry point. Existing data/business logic preserved."""
    with st.sidebar:
        st.markdown(
            '<div class="ep-brand">Executive Pulse</div>'
            '<div class="ep-brand-subtitle">Decision intelligence for leadership</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="ep-sidebar-label">Appearance</div>', unsafe_allow_html=True)
        st.radio(
            "Appearance",
            THEME_OPTIONS,
            key="ep_theme",
            horizontal=True,
            label_visibility="collapsed",
        )

        st.markdown('<div class="ep-sidebar-label">Data source</div>', unsafe_allow_html=True)
        source_type = st.radio(
            "Data Source",
            ["Sample Data", "Upload CSV/XLSX", "Google Sheet"],
            index=0,
            label_visibility="collapsed",
        )

        uploaded_file = None
        sheet_id = None
        gid = "0"

        if source_type == "Upload CSV/XLSX":
            uploaded_file = st.file_uploader(
                "Upload file",
                type=["csv", "xlsx", "xls"],
                label_visibility="collapsed",
            )
        elif source_type == "Google Sheet":
            st.caption("Share as 'Anyone with the link' or Publish to the web as CSV. Paste the ID only, not the full URL.")
            sheet_id = st.text_input("Sheet ID", placeholder="1BxiMVs0XRA5nFMd...")
            gid = st.text_input("Tab ID (digits only, blank = first tab)", value="0", placeholder="0")
            if sheet_id:
                st.caption(f"Sheet: /{sheet_id}/export · tab {gid}")

        try:
            if source_type == "Sample Data":
                df = load_data("csv")
            elif source_type == "Upload CSV/XLSX" and uploaded_file:
                df = load_data("upload", uploaded_file=uploaded_file)
            elif source_type == "Google Sheet" and sheet_id:
                df = load_data("gsheet", sheet_id=sheet_id, gid=gid)
            else:
                df = load_data("csv")
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.stop()

        st.divider()
        st.markdown('<div class="ep-sidebar-label">Navigate</div>', unsafe_allow_html=True)
        page = st.radio("Navigate", PAGES, index=0, label_visibility="collapsed")

        st.divider()
        filters = render_sidebar_filters(df)

        st.markdown(
            '<div class="ep-freshness" style="margin-top:1.5rem;">Executive Pulse</div>',
            unsafe_allow_html=True,
        )

    # Change detection against the previous snapshot (engine unchanged).
    previous_snapshot = _load_snapshot()
    changes = compute_changes(df, previous_snapshot)
    _save_snapshot(df)

    filtered_df = apply_filters(df, filters)

    if page == "Overview":
        render_overview_page(filtered_df, changes)
    elif page == "Attention":
        render_attention_page(filtered_df)
    elif page == "Decisions":
        render_decisions_page(filtered_df)
    elif page == "At Risk":
        render_risk_page(filtered_df)
    elif page == "Blocked":
        render_blocked_page(filtered_df)
    elif page == "Changes":
        render_changes_page(changes)
    elif page == "Org Pulse":
        render_org_page(filtered_df)
    elif page == "Stale Work":
        render_stale_page(filtered_df)
    elif page == "Meeting Brief":
        render_brief_page(filtered_df)
    else:
        render_detail_page(filtered_df, filters)


if __name__ == "__main__":
    main()
