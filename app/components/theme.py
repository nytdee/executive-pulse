"""
Executive Pulse theme system.

Semantic tokens with light / dark palettes. Every component references
tokens only — no hardcoded light or dark colors outside this module.
Theme switching (System / Light / Dark) works by injecting the CSS
produced here; System additionally follows the OS preference through a
prefers-color-scheme media query.
"""

from __future__ import annotations

import streamlit as st

THEME_OPTIONS = ["System", "Light", "Dark"]

LIGHT = {
    "bg": "#F5F1E8",
    "surface": "#FBF9F4",
    "surface2": "#F0ECE4",
    "elevated": "#FFFFFF",
    "text": "#17191C",
    "text2": "#62645F",
    "muted": "#8A8982",
    "border": "#DDD7CC",
    "primary": "#243B53",
    "primary_hover": "#1D3044",
    "on_primary": "#FFFFFF",
    "secondary": "#526A82",
    "accent": "#A88A5A",
    "critical": "#8B3F3B",
    "critical_bg": "#F5E9E6",
    "warning": "#9A7735",
    "warning_bg": "#F4EDDC",
    "success": "#46624D",
    "success_bg": "#E9EFE7",
    "selected": "#E5E0D7",
    "hover": "#ECE7DB",
    "input_bg": "#FBF9F4",
    "shadow": "0 1px 2px rgba(23, 25, 28, 0.06)",
}

DARK = {
    "bg": "#101418",
    "surface": "#161B20",
    "surface2": "#1D242B",
    "elevated": "#232B33",
    "text": "#F1EFE8",
    "text2": "#B8BAB5",
    "muted": "#858A8E",
    "border": "#303840",
    "primary": "#6F8AA5",
    "primary_hover": "#7F99B3",
    "on_primary": "#101418",
    "secondary": "#8FA3B8",
    "accent": "#B59A6A",
    "critical": "#C27772",
    "critical_bg": "#2A1D1C",
    "warning": "#C1A15E",
    "warning_bg": "#2A2417",
    "success": "#78977E",
    "success_bg": "#1A2420",
    "selected": "#29323A",
    "hover": "#232B33",
    "input_bg": "#161B20",
    "shadow": "0 1px 2px rgba(0, 0, 0, 0.4)",
}


def _vars(tokens: dict) -> str:
    return """:root {{
    --bg: {bg};
    --surface: {surface};
    --surface2: {surface2};
    --elevated: {elevated};
    --text: {text};
    --text2: {text2};
    --muted: {muted};
    --border: {border};
    --primary: {primary};
    --primary-hover: {primary_hover};
    --on-primary: {on_primary};
    --secondary: {secondary};
    --accent: {accent};
    --critical: {critical};
    --critical-bg: {critical_bg};
    --warning: {warning};
    --warning-bg: {warning_bg};
    --success: {success};
    --success-bg: {success_bg};
    --selected: {selected};
    --hover: {hover};
    --input-bg: {input_bg};
}}""".format(**tokens)


def _core() -> str:
    # Every rule below references tokens only.
    return r"""
/* ---------- font ---------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

/* ---------- canvas ---------- */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main {
    background: var(--bg) !important;
    color: var(--text) !important;
}

[data-testid="stMainBlockContainer"] {
    max-width: 1060px !important;
    padding-top: 2.4rem !important;
    padding-bottom: 5rem !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

p, li, label, span, div {
    letter-spacing: -0.005em;
}

h1, h2, h3, h4 {
    color: var(--text) !important;
    letter-spacing: -0.025em !important;
    font-weight: 600 !important;
}

a {
    color: var(--primary) !important;
    text-decoration: none !important;
}
a:hover {
    text-decoration: underline !important;
}

hr {
    border: 0 !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.6rem 0 !important;
}

[data-testid="stCaptionContainer"], .stCaption, small {
    color: var(--muted) !important;
}

[data-testid="stMarkdownContainer"] p {
    color: var(--text);
}

/* ---------- header / titles ---------- */
.ep-eyebrow {
    color: var(--muted);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 0.6rem;
}
.ep-title {
    color: var(--text);
    font-size: 1.9rem;
    line-height: 1.15;
    font-weight: 600;
    letter-spacing: -0.03em;
    margin: 0;
}
.ep-subtitle {
    color: var(--muted);
    font-size: 0.9rem;
    margin-top: 0.4rem;
}
.ep-state-line {
    color: var(--text);
    font-size: 1.02rem;
    margin-top: 1.2rem;
}
.ep-freshness {
    color: var(--muted);
    font-size: 0.75rem;
    margin-top: 0.4rem;
}
.ep-section {
    margin: 2.4rem 0 1rem;
}
.ep-section-title {
    color: var(--text);
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin: 0;
}
.ep-section-caption {
    color: var(--muted);
    font-size: 0.8rem;
    margin-top: 0.2rem;
}

/* ---------- executive summary strip (typographic, no cards) ---------- */
.ep-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 0 2.2rem;
    margin: 1.6rem 0 0.4rem;
    padding: 1rem 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}
.ep-summary-item {
    padding: 0;
}
.ep-summary-label {
    color: var(--muted);
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.ep-summary-value {
    color: var(--text);
    font-size: 1.5rem;
    font-weight: 600;
    margin-top: 0.25rem;
}

/* ---------- signal rows ---------- */
.sig {
    display: flex;
    gap: 0.9rem;
    padding: 0.85rem 0.2rem;
    border-bottom: 1px solid var(--border);
    align-items: flex-start;
}
.sig-bar {
    flex: 0 0 auto;
    width: 2px;
    align-self: stretch;
    border-radius: 2px;
    background: var(--primary);
}
.sig-bar.tone-critical { background: var(--critical); }
.sig-bar.tone-warning { background: var(--warning); }
.sig-bar.tone-navy { background: var(--primary); }
.sig-bar.tone-muted { background: var(--muted); }
.sig-main {
    flex: 1 1 auto;
    min-width: 0;
}
.sig-title {
    color: var(--text);
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}
.sig-meta {
    color: var(--muted);
    font-size: 0.76rem;
    margin-top: 0.15rem;
}
.sig-impact {
    color: var(--text2);
    font-size: 0.82rem;
    font-weight: 500;
    margin-top: 0.3rem;
}
.sig-signal {
    color: var(--muted);
    font-size: 0.76rem;
    margin-top: 0.15rem;
}
.sig-signal strong {
    color: var(--text2);
    font-weight: 600;
}
.sig-side {
    flex: 0 0 auto;
    padding-top: 0.1rem;
}

/* ---------- group headers ---------- */
.grp-label {
    color: var(--muted);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 1.4rem 0 0.2rem;
}
.grp-summary {
    color: var(--text2);
    font-size: 0.82rem;
    margin: 0.1rem 0 0.4rem;
}

/* ---------- decision cards ---------- */
.dec {
    padding: 1rem 0.2rem;
    border-bottom: 1px solid var(--border);
}
.dec-kicker {
    color: var(--muted);
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.dec-title {
    color: var(--text);
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 0.3rem;
}
.dec-meta {
    color: var(--muted);
    font-size: 0.78rem;
    margin-top: 0.25rem;
}

/* ---------- detail drawer ---------- */
.dw-kicker {
    color: var(--muted);
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 1.1rem 0 0.35rem;
}
.dw-kicker:first-child {
    margin-top: 0;
}
.dw-body {
    color: var(--text);
    font-size: 0.86rem;
    line-height: 1.55;
}
.dw-muted {
    color: var(--muted);
    font-size: 0.8rem;
}
.dw-score-row {
    display: flex;
    justify-content: space-between;
    color: var(--text2);
    font-size: 0.82rem;
    padding: 0.25rem 0;
    border-bottom: 1px solid var(--border);
}
.dw-score-row:last-child {
    border-bottom: 0;
}
.dw-total {
    display: flex;
    justify-content: space-between;
    color: var(--text);
    font-size: 0.86rem;
    font-weight: 600;
    padding-top: 0.4rem;
}

/* ---------- briefing document ---------- */
.brief-doc {
    max-width: 720px;
}
.brief-item {
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    font-size: 0.87rem;
}
.brief-num {
    color: var(--muted);
    font-size: 0.76rem;
    font-weight: 600;
    margin-right: 0.5rem;
}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {
    background: var(--surface2) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div {
    padding-top: 1.5rem !important;
}
section[data-testid="stSidebar"] * {
    color: var(--text) !important;
}
.ep-brand {
    color: var(--text);
    font-size: 1.02rem;
    font-weight: 600;
    letter-spacing: -0.02em;
}
.ep-brand-subtitle {
    color: var(--muted);
    font-size: 0.72rem;
    margin-top: 0.25rem;
}
.ep-sidebar-label {
    color: var(--muted);
    font-size: 0.64rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 1.3rem 0 0.4rem;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    gap: 2px !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
    border-radius: 4px !important;
    padding: 0.42rem 0.55rem !important;
    color: var(--text2) !important;
    font-size: 0.82rem !important;
    background: transparent !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: var(--hover) !important;
    color: var(--text) !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: var(--selected) !important;
    color: var(--text) !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stSelectbox,
section[data-testid="stSidebar"] .stMultiSelect,
section[data-testid="stSidebar"] .stTextInput {
    margin-bottom: 0.4rem !important;
}

/* sidebar toggle: visible in both themes, collapsed or not */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: var(--text) !important;
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg {
    color: var(--text) !important;
    opacity: 1 !important;
    fill: var(--text) !important;
}

/* ---------- inputs ---------- */
input, textarea,
[data-baseweb="select"] > div {
    background: var(--input-bg) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
    border-radius: 4px !important;
    box-shadow: none !important;
}
input:focus, textarea:focus,
[data-baseweb="select"] > div:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 1px var(--primary) !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] input {
    color: var(--text) !important;
}
div[data-baseweb="popover"] > div,
div[data-baseweb="menu"],
ul[data-baseweb="menu"] {
    background: var(--elevated) !important;
    border: 1px solid var(--border) !important;
}
div[data-baseweb="menu"] li,
ul[data-baseweb="menu"] li {
    color: var(--text) !important;
    background: transparent !important;
}
div[data-baseweb="menu"] li:hover,
ul[data-baseweb="menu"] li:hover {
    background: var(--hover) !important;
}

/* multiselect pills: neutral, never red */
[data-baseweb="tag"] {
    background: var(--selected) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
}
[data-baseweb="tag"] span {
    color: var(--text) !important;
}
[data-baseweb="tag"] svg {
    color: var(--muted) !important;
    fill: var(--muted) !important;
}

/* ---------- buttons ---------- */
.stButton > button {
    background: var(--primary) !important;
    color: var(--on-primary) !important;
    border: 1px solid var(--primary) !important;
    border-radius: 4px !important;
    box-shadow: none !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    min-height: 32px !important;
    padding: 0.35rem 0.8rem !important;
}
.stButton > button:hover {
    background: var(--primary-hover) !important;
    border-color: var(--primary-hover) !important;
    color: var(--on-primary) !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    font-weight: 500 !important;
}
.stButton > button[kind="secondary"]:hover {
    background: var(--hover) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}
.stButton > button:disabled {
    opacity: 0.45 !important;
}

/* ---------- expanders ---------- */
.stExpander, [data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stExpander"] summary,
.streamlit-expanderHeader {
    background: transparent !important;
    color: var(--text) !important;
    font-weight: 500 !important;
}
[data-testid="stExpanderDetails"],
.streamlit-expanderContent {
    background: var(--surface) !important;
    color: var(--text) !important;
    border-top: 1px solid var(--border) !important;
}

/* ---------- containers (no card grid) ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    border-radius: 4px !important;
    background: var(--surface) !important;
    box-shadow: none !important;
}

/* ---------- tables ---------- */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    overflow: hidden !important;
    background: var(--surface) !important;
}
[data-testid="stDataFrame"] * {
    color: var(--text) !important;
}
[data-testid="stTable"] thead th {
    color: var(--muted) !important;
    font-weight: 600 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    border-bottom: 1px solid var(--border) !important;
}
[data-testid="stTable"] tbody td {
    border-bottom: 1px solid var(--border) !important;
    padding-top: 0.65rem !important;
    padding-bottom: 0.65rem !important;
}

/* ---------- dialog / modal ---------- */
[data-testid="stDialog"],
[data-testid="stModal"],
div[role="dialog"] {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}
div[data-testid="stModalBlockContainer"] {
    background: var(--surface) !important;
}

/* ---------- alerts / empty states ---------- */
[data-testid="stAlert"] {
    background: var(--surface) !important;
    color: var(--text2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    box-shadow: none !important;
}
[data-testid="stAlert"] * {
    color: var(--text2) !important;
}

/* ---------- radio / checkbox / slider ---------- */
.stRadio label, .stCheckbox label {
    color: var(--text) !important;
}
[data-testid="stWidgetLabel"] {
    color: var(--text2) !important;
}
.stSlider [data-baseweb="slider"] {
    color: var(--primary) !important;
}

/* ---------- file uploader / date picker ---------- */
.stFileUploader, [data-testid="stFileUploader"] {
    background: transparent !important;
}
[data-testid="stFileUploader"] section {
    border: 1px dashed var(--border) !important;
    border-radius: 4px !important;
    background: transparent !important;
}
[data-baseweb="calendar"] {
    background: var(--elevated) !important;
    border: 1px solid var(--border) !important;
}
[data-baseweb="calendar"] * {
    color: var(--text) !important;
}

/* ---------- status text (semantic only) ---------- */
.st-critical { color: var(--critical) !important; font-weight: 600 !important; }
.st-warning { color: var(--warning) !important; font-weight: 600 !important; }
.st-ok { color: var(--success) !important; font-weight: 600 !important; }
.st-info { color: var(--primary) !important; font-weight: 600 !important; }
.st-muted { color: var(--muted) !important; }
"""


def build_css(theme: str) -> str:
    """Return the full <style> body for the requested theme mode."""
    theme = (theme or "System").strip().capitalize()
    if theme == "Dark":
        return _vars(DARK) + _core()
    if theme == "Light":
        return _vars(LIGHT) + _core()
    # System: light tokens, dark tokens under OS preference query.
    dark_vars = _vars(DARK).replace(":root", ":root", 1)
    return (
        _vars(LIGHT)
        + _core()
        + "\n@media (prefers-color-scheme: dark) {\n"
        + dark_vars
        + "\n}\n"
    )


def apply_theme() -> str:
    """Ensure theme state exists, inject CSS, return resolved theme name."""
    if "ep_theme" not in st.session_state:
        st.session_state["ep_theme"] = "System"
    theme = st.session_state.get("ep_theme", "System")
    st.markdown(f"<style>{build_css(theme)}</style>", unsafe_allow_html=True)
    return theme
