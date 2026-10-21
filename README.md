# Executive Pulse

A decision-first operating layer for time-constrained executives.

Executives do not have a shortage of data. They have a shortage of
**attention**. Executive Pulse turns operational activity — tasks,
projects, blockers, decisions — into a short, explainable list of what
actually deserves intervention right now.

```
Signal > Information
Decisions > Tasks
Clarity > Decoration
Explainability > Black-box AI
Executive Action > Dashboard Vanity Metrics
```

---

## What it does

| Module | The question it answers |
| --- | --- |
| **Attention Required** | What needs my attention right now, and why? |
| **Decisions Waiting** | What decision is blocked on me, who is waiting, and by when? |
| **At Risk** | Where could execution miss, and what is the cause? |
| **Blocked / Friction** | Where is the organization getting stuck, and who is causing it? |
| **What Changed** | What is different since my last review? |
| **Org Pulse** | Which part of the organization deserves attention? |
| **Stale Work** | What has not materially progressed? |
| **Meeting Brief** | What do I need to walk into this meeting prepared? |

Every item in the attention queue carries an explicit **"Why am I seeing
this?"** explanation. The engine is deterministic, auditable and
explainable — never a black box.

### Attention scoring

| Factor | Points |
| --- | ---: |
| Executive decision required | +5 |
| Critical impact | +5 |
| High impact | +3 |
| Blocked | +4 |
| Overdue | +4 |
| At risk (due within 48h) | +2 |
| Stale (>48h no update) | +2 |
| Dependency risk | +2 |

Bands: **10+** Critical · **7–9** High · **4–6** Watch · **0–3** Normal.
These are prioritisation bands, not predictions of failure.

---

## Architecture

This repository ships two implementations of the same product.

```
executive-pulse/
├── app/                    # Python reference engine (Streamlit)
│   ├── data/               #   loading, validation, field mapping
│   ├── engine/             #   rule engine + intelligence layer
│   └── components/         #   presentation
├── main.py                 # Streamlit application
├── tests/                  # pytest suite (84 tests)
├── scripts/
│   ├── generate_sample_data.py      # regenerates the demo dataset
│   └── generate_golden_fixtures.py  # emits the parity fixtures
└── web/                    # Next.js application (primary) — Vercel
    ├── app/                #   pages and API route handlers
    ├── components/         #   UI, design system, dashboard context
    ├── lib/                #   engine, intelligence, persona, data layer
    └── tests/              #   vitest parity suite (22 tests)
```

The **TypeScript engine in `web/lib/` is a faithful port** of the Python
reference engine. The two are held to identical behaviour by a parity
suite: `scripts/generate_golden_fixtures.py` runs a fixed dataset
through the Python engine and writes the expected output; the vitest
suite asserts the TypeScript engine reproduces it exactly — flags,
scores, bands, reason codes, ranking, org pulse, friction, owner load,
systemic risk and the meeting brief.

```bash
python scripts/generate_golden_fixtures.py   # regenerate expected output
cd web && npx vitest run                     # assert the port matches
```

If you change a rule, change it in **one** engine and regenerate the
fixtures. The suite will tell you if the other one disagrees.

---

## Running it

### Next.js (recommended — deploys to Vercel)

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm start          # serve the production build
npm test           # parity suite
```

Deploy to Vercel: import the repository, set **Root Directory** to
`web`, and deploy. The included `web/vercel.json` pins the region and
API cache headers. No environment variables are required - the app runs
on the bundled sample dataset out of the box.

### Environment variables (all optional)

| Variable | Purpose |
| --- | --- |
| `AI_API_KEY` | Enables AI field matching. Falls back to the built-in alias table without it. |
| `AI_API_BASE` | Any OpenAI-compatible endpoint. Defaults to `https://api.openai.com/v1`. |
| `AI_MODEL` | Defaults to `gpt-4o-mini`. |
| `KV_REST_API_URL` | Redis / Vercel KV REST endpoint. Enables a durable change-detection baseline. |
| `KV_REST_API_TOKEN` | The matching REST token. |

Without the KV variables the change-detection baseline lives in memory:
it resets on a serverless cold start, and it is shared between users.
That is fine for a demo. For a real deployment, set both and the
baseline persists.

### Deploying to a company

The demo runs in "public" mode - the viewer picks their lens from a
selector, and every visitor sees the same data. To run it internally:

1. **Identity.** `lib/identity.ts` defines a `SessionResolver`. Implement
   it against your provider (Auth0, Clerk, Okta, Entra) and call
   `setSessionResolver(...)`. The engine and UI do not change - the
   resolver only decides *who is looking*.
2. **Durable state.** Set the KV variables, or implement
   `SnapshotBackend` for your database.
3. **Data.** Share a Google Sheet, or upload an export. Both go through
   the same mapping layer.

### Streamlit (reference implementation)

```bash
pip install -r requirements.txt
streamlit run main.py
```

---

## API

Every intelligence module is exposed as a JSON endpoint under
`/api/v1`. Responses use one envelope:

```jsonc
{
  "ok": true,
  "data": { /* ... */ },
  "meta": {
    "generatedAt": "2026-10-21T08:00:00.000Z",
    "source": "sample",
    "total": 30,
    "filtered": 30,
    "referenceDate": "2026-10-21T08:00:00.000Z"
  }
}
```

| Endpoint | Returns |
| --- | --- |
| `GET /api/v1/tasks` | The full dataset, with filters applied |
| `GET /api/v1/attention` | The executive attention queue |
| `GET /api/v1/decisions` | The decision queue, with urgency and impact |
| `GET /api/v1/at-risk` | Work approaching a deadline or high-impact |
| `GET /api/v1/blocked` | Blocked work, grouped, with cross-team friction |
| `GET /api/v1/org-pulse` | Department rollup and risk score |
| `GET /api/v1/stale` | Work with no recent update |
| `GET /api/v1/brief` | A full meeting brief |
| `GET /api/v1/changes` | Delta since the last review |
| `GET /api/v1/health` | Service and data-source health |
| `POST /api/v1/mapping` | Map a foreign sheet onto the schema |

**Query parameters** (accepted by the read endpoints):

`source=sample|sheet` · `sheetId=<id>` · `gid=<n>` · `department=A,B` ·
`owner=A,B` · `status=A,B` · `priority=A,B` · `search=<text>` ·
`minScore=<n>` · `dateField=` · `dateFrom=` · `dateTo=` · `limit=<n>` ·
`persona=` · `focus=` · `band=`

Example:

```bash
curl "https://your-deployment.vercel.app/api/v1/attention?band=Critical&minScore=10"
```

---

## Data sources

Every source implements one adapter contract:

```ts
interface SourceAdapter {
  id: string;
  label: string;
  kind: "built-in" | "file" | "remote";
  execution: "server" | "client";
  fetch(): Promise<RawTable>;
}
```

A `RawTable` is untyped rows plus their column names. The mapping layer
then translates whatever the source calls things onto the canonical
schema. **Adding a source never touches the engine, the scoring or the
UI.**

| Adapter | Source | Where it runs |
| --- | --- | --- |
| `SampleAdapter` | The bundled demo dataset | server |
| `GoogleSheetAdapter` | A published Google Sheet | server |
| `UploadAdapter` | An uploaded `.csv` or `.xlsx` file | browser |

### Google Sheet

Paste a published sheet ID. The app maps unfamiliar column names and
status labels automatically; ambiguous fields surface a mapping panel.

### Excel / CSV

Upload a `.csv` or `.xlsx` file. **It is parsed in the browser — the
file is never uploaded to a server.** For workbooks, every sheet is
read and the largest one is offered as the default.

### AI field matching

Reporting sheets rarely use the canonical column names or the canonical
status labels. Rather than guess from a fixed alias list, the model
reads the sheet's actual columns and sample values and works out the
mapping:

```
Status: "Waiting for Decision"  ->  Blocked
         "At Risk"               ->  In Progress
         "Stale"                 ->  In Progress
```

Set `AI_API_KEY` to enable it (any OpenAI-compatible endpoint; see
`.env.example`). Without a key the built-in alias table is used
instead, and the human can correct every field either way.

The model only ever **translates labels**. It cannot change a score, a
weight or the ranking — those live in the rule engine and are not
reachable from it. Its answer is validated against the sheet before it
is used: a column it invented, or one it used twice, is discarded.

### Required schema

| Column | Type | Required |
| --- | --- | --- |
| `Task_ID` | Text | Yes |
| `Task` | Text | Yes |
| `Project` | Text | Yes |
| `Department` | Text | Yes |
| `Owner` | Text | Yes |
| `Status` | Dropdown | Yes |
| `Priority` | Dropdown | Yes |
| `Due_Date` | Date | Yes |
| `Impact` | Dropdown | Yes |
| `Last_Updated` | DateTime | Yes |
| `Executive_Decision_Required` | Yes/No | Yes |

Optional: `Owner_Role`, `Start_Date`, `Completed_Date`, `Impact_Value`,
`Blocker`, `Dependency`, `Blocker_Owner`, `Decision_By`,
`Decision_Requested`, `Source_URL`, `Notes`.

**Valid values** — Status: Not Started, In Progress, Blocked, Done, On
Hold, Overdue · Priority: Low, Medium, High, Critical · Impact: Low,
Medium, High, Critical · Decision flag: Yes/No (also accepts
true/false/1/0).

Sheets with different labels work without reformatting: mapping only
translates labels, it never alters scores, weights or ranking.

---

## The viewer lens

The product answers different questions depending on who is looking.

- **Viewing as** — CEO, CMO, CFO, CTO/CPO, COO, Chief of Staff. Groups
  the attention queue into *For you* and *Also on your radar*.
- **Your focus** — plain language: "design", "brand launches,
  partnerships". Matching items group under *For you* with the matched
  terms shown on each card.
- **My Input Required** — only the decisions waiting on *you*, scoped to
  what you own.

Both the lens and the focus profile only **group** the engine ranking.
Scores, order and reason codes are never changed, so what you see is
always what the rules produced. The lens is remembered in the browser,
so a CXO picks it once.

### Matching rules

A focus term matches case-insensitively, with prefix tolerance:

| Focus term | Matches | Does not match |
| --- | --- | --- |
| `design` | `design`, `designed`, `designing` | — |
| `launch` | `launch`, `launches` | — |
| `brand` | `brand`, `rebranding` | — |
| `marketing` | `marketing` | `market` |

The last row matters: without it, a task titled "India market launch"
would land in a Marketing exec's focus queue.

---

## Testing

```bash
python -m pytest tests/ -q    # 88 tests — reference engine
cd web && npx vitest run      # 46 tests — TypeScript/Python parity, adapters and AI mapping
```

The Python suite is path-independent and assertion-based, so it runs on
any machine and in CI. The parity suite proves the TypeScript engine
behaves identically to the Python reference, and the adapter suite
proves every data source produces the same shape of output.

### Before you push

```bash
python scripts/pre_push_check.py
```

This runs everything CI runs, plus the checks CI cannot see. It exits
non-zero if anything is wrong, so it is safe to wire into a pre-push
hook.

| Check | What it catches |
| --- | --- |
| Python reference engine tests | Broken rules |
| TypeScript test suites | Broken parity, broken adapters |
| TypeScript type check | Type errors |
| Golden fixtures in sync | A rule changed without regenerating the fixtures |
| npm lockfile in sync | `npm ci` would fail in CI |
| No secrets committed | A token or key in the working tree |
| No machine-specific paths | A hardcoded `C:\Users\…` path breaking other clones |
| No build artifacts staged | `node_modules`, `.next`, `__pycache__` about to be committed |
| No oversized files | A stray multi-megabyte file |
| README test counts accurate | The README claiming a test count that is wrong |
| Deployment env vars documented | `web/.env.example` missing |
| Production build | A build that would fail on Vercel |

To run it on every push:

```bash
# Linux / macOS
echo 'python scripts/pre_push_check.py' >> .git/hooks/pre-push
chmod +x .git/hooks/pre-push

# Windows (Git Bash)
echo 'python scripts/pre_push_check.py' >> .git/hooks/pre-push
```

Or from the web app: `cd web && npm run check`.

---

## Design principles

- No emojis, anywhere.
- Colour carries meaning, never decoration.
- Progressive disclosure: the default view shows only what an executive
  needs; everything else opens on demand.
- Typography and whitespace over boxes and borders.
- Empty states explain themselves.

---

## License

Private — all rights reserved.
