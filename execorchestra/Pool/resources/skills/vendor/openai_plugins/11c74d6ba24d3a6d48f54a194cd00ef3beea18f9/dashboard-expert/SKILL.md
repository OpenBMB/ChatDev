---
name: dashboard-expert
description: >-
  Full CRUD and analysis for Mixpanel dashboards. Use when the user asks to
  build, create, analyze, read, understand, explain, modify, update, enhance,
  or manage dashboards, or asks about dashboard layout, text cards, or report
  arrangement. Covers dashboard analysis (read + understand existing), creation
  (new builds), modification (update existing), and explanation (data-driven
  annotation).
allowed-tools: Bash Read Write
---

# Dashboard Expert

Analyze, build, modify, and explain Mixpanel dashboards. Four modes — pick the one matching the user's intent.

## Mode Selection

| User intent | Mode | Key actions |
|---|---|---|
| "analyze/understand/read/explore dashboard" | **Analyze** | Read structure, execute reports, summarize |
| "build/create/make a new dashboard" | **Build** | Investigate data → plan → create with layout |
| "modify/update/add to/fix/improve dashboard" | **Modify** | Read current state → plan changes → execute |
| "explain/annotate/add insights to dashboard" | **Explain** | Analyze → generate data-driven text cards |

## Quick Start: Analyze an Existing Dashboard

```python
import json, re
import mixpanel_headless as mp

ws = mp.Workspace()
dash = ws.get_dashboard(DASHBOARD_ID)
layout, contents = dash.layout, dash.contents

# Extract structure: rows → cells → content items
for row_id in layout["order"]:
    row = layout["rows"][row_id]
    for cell in row["cells"]:
        cid, ctype = str(cell["content_id"]), cell["content_type"]
        if ctype in ("report", "report-link"):
            info = contents["report"][cid]
            print(f"  [{cell['width']}w] {info['name']} ({info['type']}) {'[linked]' if ctype == 'report-link' else ''}")
        elif ctype == "text":
            md = contents["text"][cid].get("markdown", "")
            is_header = bool(re.search(r'<h2[\s>]', md, re.I))
            print(f"  [{cell['width']}w] TEXT {'[SECTION]' if is_header else ''}: {md[:60]}...")

# Execute each report → DataFrame
for cid, info in contents.get("report", {}).items():
    btype, bid = info["type"], info["id"]
    if btype == "flows":
        result = ws.query_saved_flows(bid)
    else:
        result = ws.query_saved_report(bid, bookmark_type=btype)
    df = result.df
    print(f"{info['name']}: {len(df)} rows, columns={list(df.columns)}")
```

## Quick Start: Build a New Dashboard

```python
from mixpanel_headless.types import CreateDashboardParams, DashboardRow, DashboardRowContent
import json

ws = mp.Workspace()
dau = ws.query("Login", math="dau", last=90)

def text(html):
    return DashboardRowContent(content_type="text", content_params={"markdown": html})

def report(name, btype, result):
    return DashboardRowContent(content_type="report", content_params={
        "bookmark": {"name": name, "type": btype, "params": json.dumps(result.params)}})

dashboard = ws.create_dashboard(CreateDashboardParams(
    title="Product Health", description="Core metrics.",
    rows=[
        DashboardRow(contents=[text("<h2>Product Health</h2><p>Core metrics.</p>")]),
        DashboardRow(contents=[report("DAU (90d)", "insights", dau)]),
    ],
))
ws.pin_dashboard(dashboard.id)  # Make visible to team
```

---

## Mode: Analyze

Read existing dashboards, execute their reports, and synthesize understanding.

### Phase A1: Read Dashboard Structure

```python
dash = ws.get_dashboard(dashboard_id)
layout, contents = dash.layout, dash.contents
```

Parse the response into a structured representation:

- **`layout["order"]`** — ordered list of row IDs
- **`layout["rows"][row_id]["cells"]`** — cells with `content_id`, `content_type`, `width`
- **`contents["report"][str(content_id)]`** — report metadata: `id` (bookmark_id), `name`, `type`, `params`, `description`
- **`contents["text"][str(content_id)]`** — text card: `markdown`

**Classify each cell:**
- `content_type == "report"` → owned, editable
- `content_type == "report-link"` → linked from another dashboard, read-only
- `content_type == "text"` → text card; detect section headers via `re.search(r'<h2[\s>]', md, re.I)`

**Build a mental model:** Group reports by section (text cards with `<h2>` tags delimit sections). Note each report's chart type, width, and position.

### Phase A2: Extract Report Details

For deeper understanding, fetch full bookmark params:

```python
bookmark = ws.get_bookmark(bookmark_id)
params = bookmark.params  # Full query definition dict
```

Key fields in params (Insights format):
- `params["sections"]["show"]` — metrics with event names and math type
- `params["sections"]["group"]` — breakdown properties
- `params["sections"]["filter"]` — active filters
- `params["sections"]["time"]` — date range
- `params["displayOptions"]["chartType"]` — visualization type

Note: `params` in `contents["report"][id]` may be a JSON string — parse with `json.loads()` if needed.

### Phase A3: Execute and Summarize

Execute each report to get live data:

```python
for cid, info in contents.get("report", {}).items():
    bid, btype = info["id"], info["type"]
    if btype == "flows":
        result = ws.query_saved_flows(bid)
    else:
        result = ws.query_saved_report(bid, bookmark_type=btype)
    df = result.df
```

**Summarize by report type:**

| Type | Key metrics to extract |
|---|---|
| insights | Total, average, latest value, min, max, trend direction |
| funnels | Step names, counts, per-step and overall conversion rate |
| retention | Day 1, Day 7, Day 30 rates; stabilization point |
| flows | Top paths, conversion rate, drop-off points |

**Cross-correlate across reports:** Look for relationships — DAU trends vs. retention, funnel drop-off vs. feature adoption.

### Phase A4: Present Analysis

Structure findings as:
1. **Dashboard overview** — title, purpose, section count, report count
2. **Section-by-section breakdown** — what each section measures, key findings
3. **Cross-metric insights** — correlations, anomalies, patterns
4. **Suggestions** — missing metrics, better chart types, layout improvements

### Multi-Dashboard Analysis

When analyzing multiple dashboards, build a unified picture:

```python
dashboard_ids = [1001, 1002, 1003]
all_data = {}
for did in dashboard_ids:
    dash = ws.get_dashboard(did)
    for cid, info in dash.contents.get("report", {}).items():
        result = ws.query_saved_report(info["id"], bookmark_type=info["type"])
        all_data[f"{dash.title}/{info['name']}"] = result.df
# Cross-dashboard: join DataFrames on date index, compute correlations
```

---

## Mode: Build

Create new dashboards from scratch. Five phases.

### Phase B1: Investigate

Before building, discover the data. Never build reports for events with zero volume.

```python
ws = mp.Workspace()
top = ws.top_events(limit=15)
for t in top:
    print(f"{t.event}: {t.count:,} ({t.percent_change:+.1%})")

# Validate candidate events
for event in candidate_events:
    result = ws.query(event, from_date="2025-01-01", to_date="2025-03-31")
    print(f"{event}: {result.df['count'].sum():,.0f} total")

# Explore properties for breakdowns
props = ws.properties(event="key_event")
values = ws.property_values(event="key_event", property="platform", limit=20)
```

### Phase B2: Plan Structure

Present a proposed structure before building. Choose a template from `references/dashboard-templates.md`.

**A plan includes:** title + description, sections with text card headers, reports per section with chart type, grid layout.

**Text cards use HTML** (not markdown). Every dashboard must have an intro text card and section headers.

**Allowed HTML tags:** `<h1>`, `<h2>`, `<h3>`, `<p>`, `<strong>`, `<em>`, `<u>`, `<s>`, `<mark>`, `<code>`, `<blockquote>`, `<hr>`, `<br>`, `<ul>`, `<ol>`, `<li>`, `<a href="...">`

**Forbidden (stripped):** `<div>`, `<span>`, `<b>` (use `<strong>`), `<i>` (use `<em>`), `<img>`, `<table>`

**Critical:** Strip `\n` and collapse whitespace from HTML before sending. Each element renders as its own line.

**Text card patterns:**
```
Intro:     <h2>Dashboard Title</h2><p>What and why. Time period: last 90 days.</p>
Section:   <h2>Acquisition</h2><p>How users discover and sign up.</p>
Explainer: <p>^ Signup conversion is <strong>23.4%</strong>, up 2.1pp.</p>
```

### Phase B3: Query and Build

Query each metric, verify data, then create with layout in one call.

```python
def text(html):
    return DashboardRowContent(content_type="text", content_params={"markdown": html})

def report(name, btype, result, description=None):
    params = {"bookmark": {"name": name, "type": btype, "params": json.dumps(result.params)}}
    if description:
        params["bookmark"]["description"] = description
    return DashboardRowContent(content_type="report", content_params=params)

dashboard = ws.create_dashboard(CreateDashboardParams(
    title="Product Health Dashboard",
    description="Key metrics for product health monitoring.",
    rows=[
        DashboardRow(contents=[text("<h2>Product Health</h2><p>Updated daily.</p>")]),
        DashboardRow(contents=[
            report("DAU (90d)", "insights", dau),
            report("Signups (90d)", "insights", signups),
            report("Revenue (90d)", "insights", revenue),
        ]),
        DashboardRow(contents=[text("<h2>Conversion</h2><p>Key funnels.</p>")]),
        DashboardRow(contents=[report("Signup Funnel", "funnels", funnel)]),
    ],
))
```

**On report failure**, substitute a fallback text card:
```python
try:
    result = ws.query(event, math="total", last=90)
    row_items.append(report(f"{event} Trend", "insights", result))
except Exception as e:
    row_items.append(text(f"<p><strong>Failed:</strong> {event} — {e}</p>"))
```

### Phase B4: Enhance

- **Pin for team visibility:** `ws.pin_dashboard(dashboard.id)` — dashboards are invisible by default
- **Favorite for personal use:** `ws.favorite_dashboard(dashboard.id)`
- **Add explainer cards:** see Mode: Explain
- **Adjust heights:** see `references/dashboard-reference.md` Section 3.4

### Phase B5: Verify

Open the dashboard and confirm all reports render with data, text cards display correctly, and layout matches the plan.

---

## Mode: Modify

Update existing dashboards. Read first, then apply changes in the correct order.

### Phase M1: Read Current State

Use Analyze Phase A1-A2 to understand the dashboard's structure. Present to user before making changes.

### Phase M2: Plan Changes

Classify each change and plan execution order. Operations **must** follow this sequence:

1. **Metadata** (title/description) — standalone PATCH
2. **Cell creates** — add new content first
3. **Row reorder** (`rows_order`) — after creates so temp IDs resolve
4. **Cell updates** — modify existing content
5. **Cell deletes** — remove content
6. **Row deletes** — remove entire rows last

### Phase M3: Execute Changes

**Adding content to a specific existing row** — send `content` AND `layout` together:

```python
import copy
dash = ws.get_dashboard(dashboard_id)
layout = copy.deepcopy(dash.layout)
target_row = layout["rows"][target_row_id]

# Redistribute widths
new_count = len(target_row["cells"]) + 1
cell_width = 12 // new_count
for cell in target_row["cells"]:
    cell["width"] = cell_width
target_row["cells"].append({"temp_id": "-1", "width": cell_width})

ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={"action": "create", "content_type": "report",
             "content_params": {"bookmark": {"name": "New Report", "type": "insights",
                                              "params": json.dumps(result.params)}}},
    layout={"rows_order": layout["order"], "rows": layout["rows"]},
))
```

**Adding content as a new row** — content action alone (appends to bottom):

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={"action": "create", "content_type": "text",
             "content_params": {"markdown": "<p>^ Explainer card.</p>"}},
))
```

**Deleting content:**

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={"action": "delete", "content_type": "report", "content_id": content_id},
))
```

**Cross-type updates** (e.g., text → report): API rejects changing `content_type` on update. Delete the old cell, then create the new one.

See `references/dashboard-reference.md` Section 8 for temp ID resolution, operation ordering details, and report-link semantics.

---

## Mode: Explain

Combine analysis with targeted text card insertion.

1. **Analyze** — run Mode: Analyze to extract structure and execute reports
2. **Generate insights** — for each report, compute key metrics from the DataFrame:
   ```python
   latest = df.iloc[-1]["count"]
   prev = df.iloc[-8]["count"]
   trend = ((latest - prev) / prev) * 100
   html = (f"<p>^ DAU is <strong>{latest:,.0f}</strong>, "
           f"{'up' if trend > 0 else 'down'} <strong>{abs(trend):.1f}%</strong> "
           f"vs. last week.</p>").replace("\n", "")
   ```
3. **Insert cards** — add as new rows below each report section:
   ```python
   ws.update_dashboard(dashboard_id, UpdateDashboardParams(
       content={"action": "create", "content_type": "text",
                "content_params": {"markdown": html}},
   ))
   ```

---

## Critical Gotchas

1. **Combined content+layout PATCH** — send both `content` and `layout` in the same `UpdateDashboardParams` to add cells to specific existing rows. Without `layout`, new content appends as a full-width row at the bottom.

2. **Width auto-redistribution** — when adding to an existing row with N cells, set all cells (including new) to `12 // (N+1)` width.

3. **Update operation ordering** — metadata → cell creates → rows_order → cell updates → cell deletes → row deletes. Wrong order causes failures.

4. **`per_user` requires `math_property`** — using per-user aggregation without a numeric property raises `BookmarkValidationError`.

5. **`CreateBookmarkParams(dashboard_id=X)` does NOT add to layout** — use `add_report_to_dashboard()` or inline content action.

6. **`add_report_to_dashboard()` CLONES** — creates "Duplicate of..." copy. Use `rows` in `CreateDashboardParams` or inline content action instead.

7. **GET `order` vs PATCH `rows_order`** — layout from GET uses `order`; PATCH expects `rows_order`.

8. **Never include `version` in layout PATCH** — the API rejects it.

9. **Strip `\n` and collapse whitespace** — call `.replace("\n", "").strip()` on text card HTML. Newlines cause TipTap to mangle content.

10. **Limits** — title 255 chars, description 400 chars, text cards 2,000 chars, max 4 items/row, max 30 rows.

11. **Cross-type cell updates require delete+create** — API rejects changing `content_type` on an update action.

12. **Report-link cells are read-only** — `content_type: "report-link"` references a report owned by another dashboard. You can view but not edit its params.

13. **Auto-pin after creation** — dashboards are invisible to the team by default. Call `ws.pin_dashboard(dashboard.id)`.

14. **The `markdown` field accepts only HTML** — despite the name. Markdown syntax renders as literal text.

## See Also

- `references/dashboard-reference.md` — Complete API reference, layout system, content actions, text card formatting, update operations, analysis patterns
- `references/dashboard-templates.md` — 9 purpose-built dashboard templates with section layouts and report specs
- `references/bookmark-pipeline.md` — End-to-end pipeline from typed query to dashboard report for all 4 engines
- `references/chart-types.md` — Chart type selection guide with slugs, use cases, and width recommendations
