# Executive Pulse

A decision-first operating layer for time-constrained executives.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

## Data Sources

The app supports three data sources (configured in the sidebar):

1. **Sample Data** - Built-in realistic dataset across 8 departments
2. **Upload CSV/XLSX** - Upload your own file with the required schema
3. **Google Sheet** - Enter a published Google Sheet ID

## Required Schema

Your data must include these columns:

| Column | Type | Required |
|--------|------|----------|
| Task_ID | Text | Yes |
| Task | Text | Yes |
| Project | Text | Yes |
| Department | Text | Yes |
| Owner | Text | Yes |
| Status | Dropdown | Yes |
| Priority | Dropdown | Yes |
| Due_Date | Date | Yes |
| Impact | Dropdown | Yes |
| Last_Updated | DateTime | Yes |
| Executive_Decision_Required | Yes/No | Yes |

Optional columns: Owner_Role, Start_Date, Completed_Date, Impact_Value, Blocker, Dependency, Blocker_Owner, Decision_By, Decision_Requested, Source_URL, Notes

### Valid Values

- **Status**: Not Started, In Progress, Blocked, Done, On Hold, Overdue
- **Priority**: Low, Medium, High, Critical
- **Impact**: Low, Medium, High, Critical
- **Executive_Decision_Required**: Yes, No (or True/False)

## Dashboard Modules

1. **Attention Required** - Top 7 highest-scored items requiring executive attention
2. **Decisions Waiting** - Items explicitly requiring executive judgment
3. **At Risk** - Upcoming deadlines with low buffer or warning conditions
4. **Blocked / Friction** - Cross-team and internal blockers grouped by department
5. **What Changed** - Delta since previous refresh (new overdue, newly blocked, resolved, status changes)
6. **Org Pulse** - Department-level rollup with open, overdue, blocked, high-impact counts
7. **Stale Work** - Items with no recent update (>48 hours)
8. **Meeting Brief** - Agenda-ready brief for a specific meeting

## Attention Scoring

The rule engine computes an attention score for each item:

| Factor | Points |
|--------|--------|
| Executive decision required | +5 |
| Critical impact | +5 |
| High impact | +3 |
| Blocked | +4 |
| Overdue | +4 |
| At risk (due within 48h) | +2 |
| Stale (>48h no update) | +2 |
| Dependency risk | +2 |

Score bands:
- **10+** Critical (red)
- **7-9** High (amber)
- **4-6** Watch (yellow)
- **0-3** Normal (green)

## Why Am I Seeing This?

Every item in the attention queue includes explicit reason codes explaining why it was surfaced (e.g., "Executive decision required + Critical impact + Overdue").

## Project Structure

```
executive_pulse/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── app/
│   ├── data/
│   │   ├── loader.py      # Data loading & validation
│   │   └── sample_data.csv # Built-in sample dataset
│   ├── engine/
│   │   └── rule_engine.py # Flags, scoring, ranking
│   ├── components/
│   │   └── ui.py          # Reusable UI components
│   ├── pages/             # Page modules (future)
│   ├── utils/             # Utility functions (future)
│   └── config/            # Configuration (future)
```

## Development

The architecture separates:
- **Data layer** (`app/data/`) - Loading, validation, filtering
- **Engine layer** (`app/engine/`) - Business logic, rules, scoring
- **Components** (`app/components/`) - Reusable UI pieces
- **Pages** (`app/pages/`) - Page-level composition (future)

This structure allows clean addition of the decision engine in Phase 2 without rebuilding the foundation.

## Non-Goals (Phase 1)

- No authentication
- No task creation workflow
- No chat/comments
- No AI recommendations
- No real-time multi-source sync
- No enterprise security features

## Attaching your own sheet

Sheets with different column names or status labels work without reformatting:

1. Select **Upload CSV/XLSX** or **Google Sheet** in the sidebar.
2. If everything resolves cleanly, the mapping happens **automatically in the backend** — the sidebar shows "Mapping: automatic".
3. If a header or value is ambiguous (e.g. `Waiting for Decision`, `At Risk`, `Stale`), a **Map your data** panel appears: match each field once and apply.
4. If the automatic guess is ever wrong, use **Adjust mapping** in the sidebar to correct it.

Multi-value dependencies (`EP-001;EP-011`) are understood. Scores, weights and ranking are never altered by mapping — it only translates labels.

## Viewing as (persona lens)

The **Viewing as** selector (CEO, CMO, CFO, CTO / CPO, COO, Chief of Staff) groups the attention queue into **For you** (your departments, engine-ranked) and **Also on your radar** (rest of the organization). Attention scores are unchanged — only grouping adapts to the viewer.

## Your focus (freeform profile)

Below **Viewing as**, the **Your focus** box accepts plain language, e.g. "brand launches, partnerships, customer escalations". Type it, press Enter, and matching signals group under **For you** with the matched terms shown on each card. Matching is title-weighted keyword overlap (no LLM, no score changes); a custom focus overrides the persona lens while active. **Clear focus** returns to the persona view.