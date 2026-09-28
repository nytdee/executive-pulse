"""
Executive Pulse - Main Streamlit Application.
A decision-first operating layer for time-constrained executives.

Presentation layer only. Data loading, rule engine, attention scoring,
ranking and filtering live in app/data, app/engine and app/components.
"""

import json
import os
import time

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
    render_mapping_panel,
    render_sidebar_filters,
    apply_filters,
    FILTER_WIDGET_KEYS,
)
from app.data.loader import (
    REQUIRED_COLUMNS,
    DataValidationError,
    load_and_validate,
    load_google_sheet,
    load_uploaded_file,
    get_data_freshness,
)
from app.data.mapping import (
    apply_mapping,
    mapping_status,
    process_mapped_frame,
    scope_key,
)
from app.engine.intelligence import get_org_pulse_enhanced, PERSONAS, extract_profile_keywords
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


# Google Sheet data goes stale fast — refetch at most this often per session.
RAW_TTL_SECONDS = 600


def _get_raw_frame(source_type: str, source_key: str, uploaded_file=None, sheet_id: str = None, gid: str = "0") -> pd.DataFrame:
    """Load an unvalidated frame, cached per attached source with a TTL."""
    now = time.time()
    cached_at = st.session_state.get("ep_raw_time", 0)
    if (
        st.session_state.get("ep_raw_key") == source_key
        and "ep_raw_frame" in st.session_state
        and now - cached_at < RAW_TTL_SECONDS
    ):
        return st.session_state["ep_raw_frame"]
    if source_type == "upload":
        uploaded_file.seek(0)
        raw = load_uploaded_file(uploaded_file)
    else:
        raw = load_google_sheet(sheet_id, gid)
    st.session_state["ep_raw_key"] = source_key
    st.session_state["ep_raw_frame"] = raw
    st.session_state["ep_raw_time"] = now
    return raw


def _refresh_data() -> None:
    """Drop all cached data so the next run refetches from the source."""
    st.cache_data.clear()
    for key in ("ep_raw_key", "ep_raw_frame", "ep_raw_time"):
        st.session_state.pop(key, None)
    st.rerun()


def _resolve_external_frame(source_type: str, source_key: str, uploaded_file=None, sheet_id: str = None, gid: str = "0"):
    """Map a foreign sheet onto the schema. Returns (df or None, pending or None)."""
    # Fresh source → drop stale filter selections referencing the old dataset.
    if st.session_state.get("ep_filter_key") != source_key:
        for widget_key in FILTER_WIDGET_KEYS:
            st.session_state.pop(widget_key, None)
        st.session_state["ep_filter_key"] = source_key

    raw = _get_raw_frame(source_type, source_key, uploaded_file, sheet_id, gid)
    skey = scope_key(source_key)
    if st.session_state.pop(f"ep-force-panel-{skey}", None):
        return None, (raw, source_key)
    confirmed = st.session_state.get(f"ep-confirmed-{skey}")

    if confirmed is not None:
        try:
            mapped = apply_mapping(raw, confirmed["columns"], confirmed.get("values", {}))
            return process_mapped_frame(mapped), None
        except DataValidationError:
            pass  # fall through to the panel so the user can fix it

    col_map, _unmapped, unknowns, suggestions = mapping_status(raw)
    needs_ui = any(col_map.get(c) is None for c in REQUIRED_COLUMNS) or bool(unknowns)
    if not needs_ui:
        auto = {
            "columns": {k: v for k, v in col_map.items() if v},
            "values": {c: dict(s) for c, s in suggestions.items()},
        }
        st.session_state[f"ep-confirmed-{skey}"] = auto
        st.session_state[f"ep-auto-{skey}"] = True
        mapped = apply_mapping(raw, auto["columns"], auto["values"])
        return process_mapped_frame(mapped), None
    return None, (raw, source_key)


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

def render_overview_page(df: pd.DataFrame, changes: dict, prev_df: pd.DataFrame = None, persona: str | None = None, profile_keywords: list | None = None) -> None:
    """Overview: state, what needs me, organization, what changed."""
    render_executive_header(df, get_data_freshness(df))

    _section("What needs your attention", "The highest-priority exceptions surfaced by the decision engine.")
    render_attention_queue(df, "What needs your attention", max_items=5, persona=persona, profile_keywords=profile_keywords)

    _section("Organization", "Where the organization is experiencing friction.")
    render_org_signal_compact(df, max_rows=5)

    _section("What changed", "Meaningful changes since your last review.")
    render_what_changed(changes, limit=5)


def render_attention_page(df: pd.DataFrame, persona: str | None = None, profile_keywords: list | None = None) -> None:
    st.markdown('<div class="ep-eyebrow">Signal</div>', unsafe_allow_html=True)
    st.markdown('<div class="ep-title">Attention</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ep-subtitle">Only items the decision engine considers worth executive time.</div>',
        unsafe_allow_html=True,
    )
    render_attention_queue(df, "Attention", max_items=7, persona=persona, profile_keywords=profile_keywords)


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

        st.markdown('<div class="ep-sidebar-label">Viewing as</div>', unsafe_allow_html=True)
        st.radio(
            "Viewing as",
            list(PERSONAS.keys()),
            index=0,
            key="ep_persona",
            label_visibility="collapsed",
        )

        st.markdown('<div class="ep-sidebar-label">Your focus</div>', unsafe_allow_html=True)
        st.text_input(
            "Your focus",
            placeholder="e.g. brand launches, partnerships…",
            key="ep_profile_text",
            label_visibility="collapsed",
        )
        _profile_text = (st.session_state.get("ep_profile_text") or "").strip()
        if _profile_text:
            _keywords = extract_profile_keywords(_profile_text)
            if _keywords:
                shown = ", ".join(_keywords[:6]) + ("…" if len(_keywords) > 6 else "")
                st.caption(f"Focusing on: {shown}")
                if st.button("Clear focus", key="ep-profile-clear", type="secondary"):
                    st.session_state.pop("ep_profile_text", None)
                    st.rerun()
            else:
                st.caption("Too vague — add a few concrete terms.")

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

        df = None
        pending_mapping = None
        source_key = "sample"
        try:
            if source_type == "Sample Data":
                df = load_data("csv")
            elif source_type == "Upload CSV/XLSX" and uploaded_file:
                source_key = f"upload:{uploaded_file.name}:{uploaded_file.size}"
                df, pending_mapping = _resolve_external_frame(
                    "upload", source_key, uploaded_file=uploaded_file,
                )
            elif source_type == "Google Sheet" and sheet_id:
                source_key = f"gsheet:{sheet_id.strip()}:{gid}"
                df, pending_mapping = _resolve_external_frame(
                    "gsheet", source_key, sheet_id=sheet_id, gid=gid,
                )
            else:
                df = load_data("csv")
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.stop()

        if source_key != "sample" and df is not None:
            skey = scope_key(source_key)
            if st.session_state.get(f"ep-confirmed-{skey}") is not None:
                is_auto = bool(st.session_state.get(f"ep-auto-{skey}"))
                st.caption(f"Mapping: {'automatic' if is_auto else 'custom'}")
                if st.button("Adjust mapping", key=f"ep-adjust-{skey}", type="secondary"):
                    st.session_state.pop(f"ep-confirmed-{skey}", None)
                    st.session_state.pop(f"ep-auto-{skey}", None)
                    st.session_state[f"ep-force-panel-{skey}"] = True
                    st.rerun()
            if st.button("Refresh data", key="ep-refresh", type="secondary"):
                _refresh_data()
            st.caption("Sheet data auto-refreshes every 10 minutes.")

        st.divider()
        st.markdown('<div class="ep-sidebar-label">Navigate</div>', unsafe_allow_html=True)
        page = st.radio("Navigate", PAGES, index=0, label_visibility="collapsed")

        st.divider()
        filters = render_sidebar_filters(df) if df is not None else None

        st.markdown(
            '<div class="ep-freshness" style="margin-top:1.5rem;">Executive Pulse</div>',
            unsafe_allow_html=True,
        )

    if df is None and pending_mapping is not None:
        raw_pending, key_pending = pending_mapping
        render_mapping_panel(raw_pending, key_pending)
        st.stop()

    # Change detection against the previous snapshot (engine unchanged).
    previous_snapshot = _load_snapshot()
    changes = compute_changes(df, previous_snapshot)
    _save_snapshot(df)

    filtered_df = apply_filters(df, filters)
    persona = st.session_state.get("ep_persona", "CEO")
    profile_text = (st.session_state.get("ep_profile_text") or "").strip()
    profile_keywords = extract_profile_keywords(profile_text) if profile_text else []

    if page == "Overview":
        render_overview_page(filtered_df, changes, persona=persona, profile_keywords=profile_keywords or None)
    elif page == "Attention":
        render_attention_page(filtered_df, persona=persona, profile_keywords=profile_keywords or None)
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
