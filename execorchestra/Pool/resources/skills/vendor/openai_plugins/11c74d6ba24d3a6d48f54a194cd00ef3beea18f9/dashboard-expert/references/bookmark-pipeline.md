# Bookmark Pipeline Reference

How typed query results become dashboard reports. Every query method returns a result with a `.params` dict ready for `CreateBookmarkParams` -- no manual JSON construction needed.

All code examples use the `mixpanel_headless` Python library.

```python
import mixpanel_headless as mp
from mixpanel_headless.types import (
    CreateBookmarkParams,
    CreateDashboardParams,
    UpdateDashboardParams,
)

ws = mp.Workspace()
```

---

## The Pipeline

Every engine follows the same four steps:

1. **Query** -- Call a typed query method to get data.
2. **Inspect** -- Check the result (`.df` for DataFrame, raw attributes).
3. **Save** -- Create a bookmark with `CreateBookmarkParams` using `result.params`.
4. **Place** -- Add the bookmark to a dashboard.

The key advantage: `.params` is generated automatically by the typed query methods. The dict contains the exact bookmark parameters Mixpanel needs. You never construct bookmark JSON by hand.

---

## Engine 1: Insights

```python
# 1. Query
result = ws.query("Login", math="dau", group_by="platform", last=90)

# 2. Inspect
print(result.df.describe())
print(f"Total: {result.df['count'].sum():,.0f}")

# 3. Save as bookmark
# Assumes `dashboard` was created earlier via ws.create_dashboard(...)
bookmark = ws.create_bookmark(CreateBookmarkParams(
    name="DAU by Platform (90d)",
    bookmark_type="insights",
    params=result.params,
    description="Daily active users segmented by platform.",
    dashboard_id=dashboard.id,
))

# 4. Place on dashboard
ws.add_report_to_dashboard(dashboard.id, bookmark.id)
```

Key parameters: `events` (str or list), `math` (`"total"`, `"dau"`, `"wau"`, `"mau"`, etc.), `group_by`, `where` (Filter), `last` (days, default 30), `from_date`/`to_date`.

---

## Engine 2: Funnels

```python
# 1. Query
result = ws.query_funnel(
    steps=["Page View", "Signup Started", "Signup Completed", "First Action"],
    from_date="2025-01-01",
    to_date="2025-03-31",
)

# 2. Inspect
print(result.df)
for step in result.steps:
    print(f"  {step['name']}: {step['count']:,}")

# 3. Save as bookmark
bookmark = ws.create_bookmark(CreateBookmarkParams(
    name="Signup Conversion Funnel",
    bookmark_type="funnels",
    params=result.params,
    dashboard_id=dashboard.id,
))

# 4. Place on dashboard
ws.add_report_to_dashboard(dashboard.id, bookmark.id)
```

Key parameters: `steps` (list of str, min 2), `conversion_window` (default 14), `conversion_window_unit`, `order` (`"loose"` or `"any"`), `group_by`, `where`, `last`/`from_date`/`to_date`.

---

## Engine 3: Retention

```python
# 1. Query
result = ws.query_retention(
    born_event="Signup",
    return_event="Login",
    from_date="2025-01-01",
    to_date="2025-03-31",
    alignment="birth",
)

# 2. Inspect
print(result.df)
print(f"Average retention: {result.average:.1%}")

# 3. Save
bookmark = ws.create_bookmark(CreateBookmarkParams(
    name="New User Retention (D1-D30)",
    bookmark_type="retention",
    params=result.params,
    dashboard_id=dashboard.id,
))

# 4. Place on dashboard
ws.add_report_to_dashboard(dashboard.id, bookmark.id)
```

Key parameters: `born_event`, `return_event`, `retention_unit` (`"day"`, `"week"`, `"month"`), `alignment` (`"birth"` or `"calendar"`), `bucket_sizes` (custom intervals), `last`/`from_date`/`to_date`.

---

## Engine 4: Flows

```python
# 1. Query
result = ws.query_flow(
    event="Signup",
    forward=5,
    count_type="unique",
    from_date="2025-01-01",
    to_date="2025-03-31",
)

# 2. Inspect
print(result.df.head())  # Top paths

# 3. Save
bookmark = ws.create_bookmark(CreateBookmarkParams(
    name="Post-Signup User Journeys",
    bookmark_type="flows",
    params=result.params,
    dashboard_id=dashboard.id,
))

# 4. Place on dashboard
ws.add_report_to_dashboard(dashboard.id, bookmark.id)
```

Key parameters: `event` (str), `forward` (steps after, default 3), `reverse` (steps before, default 0), `count_type` (`"unique"`, `"total"`, `"session"`), `collapse_repeated`, `last`/`from_date`/`to_date`.

---

## Alternative: Inline Report Creation

Create reports directly on dashboards without creating separate bookmarks. This is the **preferred method** -- no cloning, no "Duplicate of ..." prefix, single API call.

```python
import json

# Query any engine
result = ws.query("Login", math="dau", last=30)

# Create report directly on dashboard
ws.update_dashboard(dashboard.id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "report",
        "content_params": {
            "bookmark": {
                "name": "Daily Active Users",
                "type": "insights",
                "params": json.dumps(result.params),
                "description": "DAU over the last 30 days.",
            }
        },
    }
))
```

**With inline creation, `params` must be a JSON string (`json.dumps(result.params)`), not a dict.** This is the most common mistake. The bookmark API accepts a dict; the inline content action accepts a JSON string.

---

## Bookmark Types

| Engine | `bookmark_type` value | Query method |
|---|---|---|
| Insights | `"insights"` | `ws.query()` |
| Funnels | `"funnels"` | `ws.query_funnel()` |
| Retention | `"retention"` | `ws.query_retention()` |
| Flows | `"flows"` | `ws.query_flow()` |

---

## Common Mistakes

### 1. Wrong bookmark type string

```python
# WRONG -- singular
bookmark_type="funnel"
bookmark_type="flow"

# CORRECT -- plural for funnels, plural for flows
bookmark_type="funnels"
bookmark_type="flows"
```

### 2. Forgetting json.dumps() for inline creation

```python
# WRONG -- dict for inline content action
"params": result.params

# CORRECT -- JSON string for inline content action
"params": json.dumps(result.params)
```

Note: `CreateBookmarkParams.params` accepts a dict. Only inline content actions need `json.dumps()`.

### 3. Expecting dashboard_id to place the report

```python
# WRONG -- this associates metadata, does NOT add to the layout
ws.create_bookmark(CreateBookmarkParams(
    name="Report",
    bookmark_type="insights",
    params=result.params,
    dashboard_id=dashboard.id,  # required, but does not place on layout
))
# You must ALSO call add_report_to_dashboard() or use inline creation
```

### 4. Not inspecting data before saving

```python
# WRONG -- save without checking
bookmark = ws.create_bookmark(CreateBookmarkParams(...))

# CORRECT -- verify the query returned meaningful data
result = ws.query("Login", math="dau", last=30)
if result.df.empty:
    print("No data -- skipping this report")
else:
    bookmark = ws.create_bookmark(CreateBookmarkParams(
        name="DAU", bookmark_type="insights",
        params=result.params, dashboard_id=dashboard.id,
    ))
```

### 5. Using wrong parameter names from other APIs

```python
# WRONG -- these are not the actual parameter names
ws.query_funnel(events=["A", "B"])       # parameter is "steps", not "events"
ws.query_flow(from_event="A", steps=5)   # parameter is "event" and "forward"
ws.query_retention(retention_type="birth")  # parameter is "alignment"
```

---

## End-to-End: Multi-Engine Dashboard

A complete example building a dashboard with one report from each query engine.

```python
import json
import mixpanel_headless as mp
from mixpanel_headless.types import (
    CreateDashboardParams,
    UpdateDashboardParams,
)

ws = mp.Workspace()

# Create the dashboard
dashboard = ws.create_dashboard(CreateDashboardParams(
    title="Product Overview",
    description="Key metrics across all analytics dimensions.",
))

# Add intro text card
ws.update_dashboard(dashboard.id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "text",
        "content_params": {
            "markdown": (
                "<h2>Product Overview</h2>"
                "<p>Key metrics across all analytics dimensions.</p>"
            )
        },
    }
))

# Query all 4 engines
dau = ws.query("Login", math="dau", last=30)
funnel = ws.query_funnel(
    steps=["Signup", "Onboarding", "First Action"],
    last=90,
)
retention = ws.query_retention(
    born_event="Signup",
    return_event="Login",
    last=90,
)
flows = ws.query_flow(
    event="Signup",
    forward=5,
    last=30,
)

# Add each report inline (preferred -- no cloning, no separate bookmarks)
reports = [
    ("Daily Active Users", "insights", dau),
    ("Signup Funnel", "funnels", funnel),
    ("New User Retention", "retention", retention),
    ("Post-Signup Journeys", "flows", flows),
]

for name, btype, result in reports:
    if result.df.empty:
        print(f"Skipping {name} -- no data")
        continue
    ws.update_dashboard(dashboard.id, UpdateDashboardParams(
        content={
            "action": "create",
            "content_type": "report",
            "content_params": {
                "bookmark": {
                    "name": name,
                    "type": btype,
                    "params": json.dumps(result.params),
                }
            },
        }
    ))

print(f"Dashboard created: {dashboard.id}")
```

This creates a dashboard with 5 items: one text card header and four reports, one from each query engine. All reports use inline creation to avoid cloning artifacts.
