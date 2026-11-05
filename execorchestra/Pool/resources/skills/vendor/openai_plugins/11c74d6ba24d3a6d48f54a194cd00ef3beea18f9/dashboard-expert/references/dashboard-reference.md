# Dashboard Reference

Exhaustive technical reference for Mixpanel dashboard creation, layout, content actions, text card formatting, time filters, and known gotchas. Consult this when you need exact parameter names, field types, API behaviors, or formatting rules.

All code examples use the `mixpanel_headless` Python library.

```python
import mixpanel_headless as mp
from mixpanel_headless.types import (
    CreateDashboardParams,
    UpdateDashboardParams,
    UpdateTextCardParams,
    UpdateReportLinkParams,
    Dashboard,
)

ws = mp.Workspace()
```

---

## 1. API Reference

### 1.1 Types

#### CreateDashboardParams

Import: `from mixpanel_headless.types import CreateDashboardParams`

| Field | Type | Default | Constraints |
|---|---|---|---|
| `title` | `str` | **required** | Max 255 chars |
| `description` | `str \| None` | `None` | Max 400 chars |
| `is_private` | `bool \| None` | `None` (False) | |
| `is_restricted` | `bool \| None` | `None` (False) | |
| `filters` | `list[Any] \| None` | `None` | Dashboard-level filters |
| `breakdowns` | `list[Any] \| None` | `None` | Dashboard-level breakdowns |
| `time_filter` | `Any \| None` | `None` | Dashboard-level time filter (see Section 5) |
| `duplicate` | `int \| None` | `None` | ID of dashboard to duplicate |

```python
params = CreateDashboardParams(
    title="Product Health Dashboard",
    description="Key metrics for monitoring product health.",
)
```

#### UpdateDashboardParams

Import: `from mixpanel_headless.types import UpdateDashboardParams`

All fields are optional. Only provided fields are sent to the API.

| Field | Type | Default | Constraints |
|---|---|---|---|
| `title` | `str \| None` | `None` | Max 255 chars |
| `description` | `str \| None` | `None` | Max 400 chars |
| `is_private` | `bool \| None` | `None` | |
| `is_restricted` | `bool \| None` | `None` | |
| `filters` | `list[Any] \| None` | `None` | Dashboard-level filters |
| `breakdowns` | `list[Any] \| None` | `None` | Dashboard-level breakdowns |
| `time_filter` | `Any \| None` | `None` | Dashboard-level time filter |
| `layout` | `Any \| None` | `None` | Layout patch (see Section 3) |
| `content` | `Any \| None` | `None` | Content action (see Section 2) |

```python
params = UpdateDashboardParams(title="Q1 Metrics v2")
data = params.model_dump(exclude_none=True)
# {"title": "Q1 Metrics v2"}
```

#### UpdateTextCardParams

Import: `from mixpanel_headless.types import UpdateTextCardParams`

| Field | Type | Default | Notes |
|---|---|---|---|
| `markdown` | `str \| None` | `None` | HTML content for the text card (see Section 4) |

Model config: `extra="allow"` -- additional fields are preserved.

```python
params = UpdateTextCardParams(markdown="<h2>Section Title</h2><p>Description.</p>")
```

#### UpdateReportLinkParams

Import: `from mixpanel_headless.types import UpdateReportLinkParams`

| Field | Type | Default | Notes |
|---|---|---|---|
| `link_type` | `str` | **required** | Serialized as `"type"` via alias. Example: `"embedded"` |

Model config: `populate_by_name=True, extra="allow"`.

```python
params = UpdateReportLinkParams(link_type="embedded")
data = params.model_dump(by_alias=True, exclude_none=True)
# {"type": "embedded"}
```

#### Dashboard (response model)

Import: `from mixpanel_headless.types import Dashboard`

The `Dashboard` model uses `extra="allow"` so new API fields are preserved automatically. Key fields:

| Field | Type | Description |
|---|---|---|
| `id` | `int` | Unique dashboard identifier |
| `title` | `str` | Dashboard title |
| `description` | `str \| None` | Dashboard description |
| `is_private` | `bool` | Whether dashboard is private |
| `is_restricted` | `bool` | Whether access is restricted |
| `creator_id` | `int \| None` | Creator's user ID |
| `creator_name` | `str \| None` | Creator's name |
| `creator_email` | `str \| None` | Creator's email |
| `created` | `datetime \| str \| None` | Creation timestamp |
| `modified` | `datetime \| str \| None` | Last modification timestamp |
| `is_favorited` | `bool \| None` | Whether current user favorited it |
| `pinned_date` | `str \| None` | Date pinned, if any |
| `layout_version` | `str \| None` | Layout version metadata |
| `unique_view_count` | `int \| None` | Number of unique viewers |
| `total_view_count` | `int \| None` | Total view count |

The `layout` field (from `get_dashboard`) contains the full layout structure described in Section 3.

### 1.2 Workspace Methods

#### List dashboards

```python
def list_dashboards(self, *, ids: list[int] | None = None) -> list[Dashboard]
```

Retrieves all dashboards visible to the authenticated user, optionally filtered by specific IDs.

```python
dashboards = ws.list_dashboards()
dashboards = ws.list_dashboards(ids=[101, 102, 103])
```

#### Create dashboard

```python
def create_dashboard(self, params: CreateDashboardParams) -> Dashboard
```

Creates a new dashboard. Returns the newly created `Dashboard`.

```python
dashboard = ws.create_dashboard(CreateDashboardParams(title="Q1 Metrics"))
print(dashboard.id)  # Use this ID for all subsequent operations
```

#### Get dashboard

```python
def get_dashboard(self, dashboard_id: int) -> Dashboard
```

Retrieves a single dashboard by ID. The response includes the full `layout` structure with row IDs, cell IDs, and content IDs needed for layout patching.

```python
dash = ws.get_dashboard(dashboard_id)
# Access layout: dash.layout["order"], dash.layout["rows"]
```

#### Update dashboard

```python
def update_dashboard(self, dashboard_id: int, params: UpdateDashboardParams) -> Dashboard
```

Updates an existing dashboard. Only provided fields are modified. Returns the updated `Dashboard`.

Used for three distinct operations:
1. **Metadata updates** -- title, description, privacy, time filter
2. **Content actions** -- add/remove/update reports and text cards (via `content` field)
3. **Layout patches** -- rearrange rows, resize cells (via `layout` field)

```python
# Metadata update
ws.update_dashboard(dashboard_id, UpdateDashboardParams(title="New Title"))

# Content action (see Section 2)
ws.update_dashboard(dashboard_id, UpdateDashboardParams(content={...}))

# Layout patch (see Section 3)
ws.update_dashboard(dashboard_id, UpdateDashboardParams(layout={...}))
```

#### Delete dashboard

```python
def delete_dashboard(self, dashboard_id: int) -> None
```

Permanently deletes a dashboard. No return value.

#### Bulk delete dashboards

```python
def bulk_delete_dashboards(self, ids: list[int]) -> None
```

Deletes multiple dashboards in a single API call.

```python
ws.bulk_delete_dashboards([101, 102, 103])
```

#### Favorite / unfavorite dashboard

```python
def favorite_dashboard(self, dashboard_id: int) -> None
def unfavorite_dashboard(self, dashboard_id: int) -> None
```

Toggles the current user's favorite status on a dashboard. Favorited dashboards appear in the user's favorites list in the Mixpanel UI.

#### Pin / unpin dashboard

```python
def pin_dashboard(self, dashboard_id: int) -> None
def unpin_dashboard(self, dashboard_id: int) -> None
```

Pinned dashboards appear at the top of the dashboard list for all project members.

#### Add report to dashboard

```python
def add_report_to_dashboard(self, dashboard_id: int, bookmark_id: int) -> Dashboard
```

**CLONES** the specified bookmark onto the dashboard. The original bookmark is unchanged. The cloned report gets a new content ID and appears with a "Duplicate of ..." name prefix. Returns the updated `Dashboard`.

**Prefer inline content actions (Section 2) over this method** to avoid cloning behavior.

```python
updated_dash = ws.add_report_to_dashboard(dashboard_id, bookmark_id)
```

#### Remove report from dashboard

```python
def remove_report_from_dashboard(self, dashboard_id: int, bookmark_id: int) -> Dashboard
```

Removes a report from a dashboard by its bookmark/report ID. Returns the updated `Dashboard`.

```python
ws.remove_report_from_dashboard(dashboard_id, report_id)
```

#### Update text card

```python
def update_text_card(self, dashboard_id: int, text_card_id: int, params: UpdateTextCardParams) -> None
```

Updates a text card's content. The `text_card_id` is the content ID from the layout.

```python
ws.update_text_card(dashboard_id, text_card_id, UpdateTextCardParams(
    markdown="<h2>Updated Title</h2><p>New description.</p>"
))
```

#### Update report link

```python
def update_report_link(self, dashboard_id: int, report_link_id: int, params: UpdateReportLinkParams) -> None
```

Updates a report link on a dashboard.

```python
ws.update_report_link(dashboard_id, report_link_id, UpdateReportLinkParams(link_type="embedded"))
```

---

## 2. Content Actions

Content actions add, remove, and modify items on a dashboard via the `content` field of `UpdateDashboardParams`. Each action is a dictionary with `action`, `content_type`, and action-specific fields.

### Content types

| Type | Description |
|---|---|
| `report` | A report card (insights, funnels, retention, flows) |
| `text` | A text/markdown card |

### Actions

| Action | Description |
|---|---|
| `create` | Add new content to the dashboard |
| `delete` | Remove content from the dashboard |
| `update` | Modify existing content in place |
| `move` | Move content to a different position (prefer layout PATCH — Section 3 — instead) |
| `duplicate` | Duplicate content within the dashboard |
| `undelete` | Restore previously deleted content |

### 2.1 Create text card

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "text",
        "content_params": {
            "markdown": "<h2>Section Title</h2><p>Brief description of this section.</p>"
        },
    }
))
```

The new text card is appended to the bottom of the dashboard. Rearrange via layout patch (Section 3) afterward.

### 2.2 Create report from existing bookmark (clones it)

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "report",
        "content_params": {
            "source_bookmark_id": bookmark_id
        },
    }
))
```

This clones the bookmark onto the dashboard. The original bookmark is unchanged. The clone gets a new content ID.

### 2.3 Create report inline (preferred)

```python
import json

ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "report",
        "content_params": {
            "bookmark": {
                "name": "Daily Active Users",
                "type": "insights",
                "params": json.dumps(result.params),
                "description": "DAU trend over the last 90 days.",
            }
        },
    }
))
```

**This is the preferred method.** It creates the report directly on the dashboard without cloning, without creating a separate bookmark entity, and without the "Duplicate of ..." name prefix.

Supported `type` values: `"insights"`, `"funnels"`, `"retention"`, `"flows"`

The `params` field must be a JSON string (use `json.dumps()`), not a dict.

### 2.4 Delete content

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "delete",
        "content_type": "report",  # or "text"
        "content_id": content_id,
    }
))
```

The `content_id` is the numeric ID from the layout cells.

### 2.5 Update text card content

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "update",
        "content_type": "text",
        "content_id": text_card_id,
        "content_params": {
            "markdown": "<h2>Updated Title</h2><p>New description.</p>"
        },
    }
))
```

### 2.6 Duplicate content

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "duplicate",
        "content_type": "report",
        "content_id": content_id,
    }
))
```

### 2.7 Undelete content

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "undelete",
        "content_type": "report",
        "content_id": content_id,
    }
))
```

---

## 3. Layout System

### 3.1 Grid Fundamentals

- **12 columns** per row (`ROW_TOTAL_WIDTH = 12`)
- **Max 4 items** per row
- **Max 30 rows** per dashboard
- **Layout version:** `"2.0.0"`
- **Standard widths:** 3 (quarter), 4 (third), 6 (half), 12 (full)
- Cell widths in a row must sum to exactly 12

### 3.2 Layout Structure from GET

When you call `ws.get_dashboard(id)`, the layout is returned in this structure:

```json
{
  "version": "2.0.0",
  "order": ["row-abc-123", "row-def-456"],
  "rows": {
    "row-abc-123": {
      "height": 0,
      "cells": [
        {
          "id": "cell-aaa-111",
          "width": 12,
          "content_id": 90001,
          "content_type": "text"
        }
      ]
    },
    "row-def-456": {
      "height": 336,
      "cells": [
        {
          "id": "cell-bbb-222",
          "width": 4,
          "content_id": 90002,
          "content_type": "report"
        },
        {
          "id": "cell-ccc-333",
          "width": 4,
          "content_id": 90003,
          "content_type": "report"
        },
        {
          "id": "cell-ddd-444",
          "width": 4,
          "content_id": 90004,
          "content_type": "report"
        }
      ]
    }
  }
}
```

Key fields:

| Field | Description |
|---|---|
| `version` | Always `"2.0.0"`. **Never include in PATCH.** |
| `order` | Ordered list of row IDs. **Called `order` in GET response.** |
| `rows` | Dict mapping row ID to `{height, cells}`. |
| `rows[].height` | Row height in pixels. `0` means auto (text-only rows). |
| `rows[].cells` | Ordered list of cells in the row. |
| `cells[].id` | Cell identifier (UUID string). |
| `cells[].width` | Cell width (1-12). Sum of all cells in a row must equal 12. |
| `cells[].content_id` | Numeric ID of the content item. |
| `cells[].content_type` | One of: `"text"`, `"report"`. |

### 3.3 Layout PATCH Format

When patching layout via `UpdateDashboardParams(layout=...)`, use this format. **Critical: `rows` must be a list (not a dict).** The GET response returns rows as a dict keyed by row ID, but the PATCH expects a list with `id` on each row object.

```json
{
  "rows_order": ["row-abc-123", "row-def-456"],
  "rows": [
    {
      "id": "row-abc-123",
      "height": 0,
      "cells": [
        {
          "id": "cell-aaa-111",
          "width": 12,
          "content_id": 90001,
          "content_type": "text"
        }
      ]
    },
    {
      "id": "row-def-456",
      "height": 418,
      "cells": [
        {
          "id": "cell-bbb-222",
          "width": 6,
          "content_id": 90002,
          "content_type": "report"
        },
        {
          "id": "cell-ccc-333",
          "width": 6,
          "content_id": 90003,
          "content_type": "report"
        }
      ]
    }
  ]
}
```

**Critical differences from GET:**

| GET response | PATCH payload |
|---|---|
| `"order"` | `"rows_order"` |
| `"rows"` is a **dict** keyed by row ID | `"rows"` is a **list** with `"id"` on each row |
| Includes `"version"` | **Never include `"version"`** |

### 3.4 Complete Layout Patch Example

```python
# 1. Get current layout to discover IDs
dash = ws.get_dashboard(dashboard_id)
layout = dash.layout  # dict with version, order, rows

# 2. Extract existing row/cell IDs and content IDs
# (IDs are auto-generated UUIDs; you must read them, not invent them)

# 3. Build the patch — rows_order (not order), rows as LIST (not dict)
row_ids = list(layout["order"])  # preserve current order, or rearrange
rows_list = []
for row_id in row_ids:
    row = layout["rows"][row_id]
    rows_list.append({
        "id": row_id,
        "height": row.get("height", 0),
        "cells": row.get("cells", []),
    })

ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    layout={"rows_order": row_ids, "rows": rows_list}
))
```

### 3.5 Width Assignment Table

| Content | Width | Rationale |
|---|---|---|
| Text card (section header) | 12 | Always full width |
| KPI metric card | 3 or 4 | Pack 3-4 per row |
| Line/bar chart (paired) | 6 | Side-by-side comparison |
| Line/bar chart (solo) | 12 | Full width for detail |
| Table | 12 | Needs full width for columns |
| Funnel (3+ steps) | 12 | Complex funnels need space |
| Retention curve | 12 | Full width for cohort grid |
| Sankey/flow | 12 | Always full width |

### 3.6 Height Guidelines

| Row Configuration | Height (px) | Notes |
|---|---|---|
| Text-only row | 0 | Auto height, expands to fit content |
| KPI row (3-4 metric cards) | 336 | Compact number display |
| Two charts side-by-side (6+6) | 418 | Standard chart height |
| Single full-width chart | 500 | More vertical space for detail |
| Full-width funnel or table | 588 | Extra space for steps/rows |

Heights are guidelines. The Mixpanel UI allows manual resizing. Use `0` for text-only rows to let them auto-size.

---

## 4. Text Card Formatting

Text cards use a restricted subset of HTML. Mixpanel's frontend renders them through a TipTap editor which sanitizes input and only supports specific tags.

### 4.1 Allowed HTML Tags

| Category | Tags | Notes |
|---|---|---|
| Headings | `<h1>`, `<h2>`, `<h3>` | Prefer `<h2>` and `<h3>`. Avoid `<h1>` (too large for dashboard cards). |
| Text | `<p>`, `<strong>`, `<em>`, `<u>`, `<s>`, `<mark>`, `<code>` | Use `<strong>` not `<b>`. Use `<em>` not `<i>`. |
| Structure | `<blockquote>`, `<hr>`, `<br>` | `<blockquote>` renders as indented block with left border. |
| Lists | `<ul>`, `<ol>`, `<li>` | Nested lists are supported. |
| Links | `<a href="...">` | External links open in new tab. |

### 4.2 Tags That Will Be STRIPPED

These tags are silently removed by the sanitizer. Your content will render without them, potentially breaking layout:

| Tag | Reason | Use Instead |
|---|---|---|
| `<div>` | Stripped by sanitizer | `<p>` |
| `<span>` | Stripped by sanitizer | Inline formatting tags (`<strong>`, `<em>`, etc.) |
| `<b>` | Non-semantic | `<strong>` |
| `<i>` | Non-semantic | `<em>` |
| `<img>` | Not supported | — |
| `<table>`, `<tr>`, `<td>`, `<th>` | Not supported | Use a report card with table chart type |
| Any inline `style` attributes | Stripped | Use semantic tags |
| Any `class` attributes | Stripped | Use semantic tags |

### 4.3 Formatting Rules

1. **Strip all `\n` newlines and collapse whitespace before sending.** Mixpanel's TipTap editor takes a markdown-it code path that mangles HTML when newlines are present. Always call `.replace("\n", "").strip()` on the markdown string. Multiple spaces or tabs can also cause rendering issues.

2. **Each HTML element renders as a new line** in the card. A `<p>` tag produces one visual line. Two consecutive `<p>` tags produce two lines. Do not try to use `\n` for line breaks.

3. **Character limit:** Practical limit is 2,000 characters. Keep text cards under 500 characters for readability. Dashboard cards have limited vertical space.

4. **No Markdown syntax.** Despite the field being called `markdown`, it accepts only HTML. Do not send `# Heading` or `**bold**` -- use `<h2>Heading</h2>` and `<strong>bold</strong>`.

5. **Section header pattern:** `<h2>Section Title</h2><p>One sentence description.</p>` -- keep section titles to 2-4 words.

6. **Explainer pattern:** `<p>^ Brief data-driven insight about the chart above.</p>` -- the `^` caret is a visual convention indicating this card explains the chart directly above it.

### 4.4 Text Card Templates

#### Dashboard intro

```python
markdown = (
    "<h2>Product Health Dashboard</h2>"
    "<p>Core metrics for monitoring product health. Updated daily.</p>"
)
```

#### Section header

```python
markdown = (
    "<h2>Growth Trends</h2>"
    "<p>User acquisition and activation metrics over time.</p>"
)
```

#### Explainer card (data-driven)

```python
markdown = (
    f"<p>^ DAU is <strong>{latest_dau:,.0f}</strong>, "
    f"{'up' if trend > 0 else 'down'} "
    f"<strong>{abs(trend):.1f}%</strong> vs. last week.</p>"
).replace("\n", "")
```

#### Methodology note

```python
markdown = (
    "<p><em>Methodology:</em> DAU counts unique users who triggered "
    "any event in a calendar day. Excludes bot traffic.</p>"
)
```

#### Key takeaway

```python
markdown = (
    "<h3>Key Takeaway</h3>"
    "<p>Mobile conversion is <strong>2.3x higher</strong> than desktop. "
    "Prioritize mobile onboarding improvements.</p>"
)
```

#### Warning / caveat

```python
markdown = (
    "<p><strong>Note:</strong> Data prior to Jan 15 reflects the old "
    "tracking schema. Direct comparison across that boundary is unreliable.</p>"
)
```

#### Bullet list summary

```python
markdown = (
    "<h3>Q1 Highlights</h3>"
    "<ul>"
    "<li>DAU grew <strong>18%</strong> quarter-over-quarter</li>"
    "<li>Signup funnel conversion improved from 12% to 15%</li>"
    "<li>7-day retention stable at <strong>42%</strong></li>"
    "</ul>"
)
```

#### Blockquote callout

```python
markdown = (
    "<blockquote>This dashboard covers the core product loop: "
    "acquisition, activation, retention. For revenue metrics, "
    "see the Revenue Dashboard.</blockquote>"
)
```

### 4.5 Sending Text Card Content

Always strip newlines before sending:

```python
# Build multi-line for readability in code
markdown = (
    "<h2>Section Title</h2>"
    "<p>Description paragraph one.</p>"
    "<p>Description paragraph two.</p>"
)

# Strip newlines (critical -- TipTap mangles HTML with newlines)
clean_markdown = markdown.replace("\n", "")

# Send via content action
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "text",
        "content_params": {"markdown": clean_markdown},
    }
))

# Or update existing text card directly
ws.update_text_card(dashboard_id, text_card_id, UpdateTextCardParams(
    markdown=clean_markdown
))
```

---

## 5. Dashboard Time Filters

Dashboard-level time filters override individual report time ranges. Set them at creation time or via update.

### 5.1 "Last N days" (rolling window)

```python
time_filter = {
    "dateRange": {
        "type": "in the last",
        "window": {"unit": "day", "value": 30}
    },
    "displayText": "Last 30 days"
}

dashboard = ws.create_dashboard(CreateDashboardParams(
    title="Rolling 30-Day Metrics",
    time_filter=time_filter,
))
```

Window units: `"day"`, `"week"`, `"month"`

### 5.2 "Since date" (open-ended)

```python
time_filter = {
    "dateRange": {
        "type": "since",
        "from_date": "2025-01-01"
    },
    "displayText": "Since Jan 1, 2025"
}

dashboard = ws.create_dashboard(CreateDashboardParams(
    title="2025 Metrics",
    time_filter=time_filter,
))
```

### 5.3 "Between dates" (fixed range)

```python
time_filter = {
    "dateRange": {
        "type": "between",
        "from_date": "2025-01-01",
        "to": "2025-03-31"
    },
    "displayText": "Jan 1 - Mar 31, 2025"
}

dashboard = ws.create_dashboard(CreateDashboardParams(
    title="Q1 2025 Metrics",
    time_filter=time_filter,
))
```

### 5.4 Updating time filter on existing dashboard

```python
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    time_filter={
        "dateRange": {
            "type": "in the last",
            "window": {"unit": "week", "value": 4}
        },
        "displayText": "Last 4 weeks"
    }
))
```

### 5.5 Removing time filter

```python
# Set to empty dict or None to remove dashboard-level time filter
ws.update_dashboard(dashboard_id, UpdateDashboardParams(time_filter={}))
```

### 5.6 Dashboard-Level Filters and Breakdowns

`CreateDashboardParams` accepts `filters` and `breakdowns` fields. These apply globally across all reports on the dashboard. In practice, dashboard-level filters are primarily configured through the Mixpanel UI. The API fields are useful for:

- **Preserving existing filters** when updating a dashboard programmatically
- **Reading filters** from `get_dashboard()` to understand the dashboard's scope

```python
# Read existing dashboard-level filters
dash = ws.get_dashboard(dashboard_id)
print(dash.filters)     # list of filter dicts, or None
print(dash.breakdowns)  # list of breakdown dicts, or None
```

---

## 6. Critical Gotchas

### 6.1 CreateBookmarkParams(dashboard_id=X) does NOT add to layout

The `dashboard_id` field on `CreateBookmarkParams` exists but only sets internal metadata. It does **not** place the report on the dashboard layout. You must use one of:
- `ws.add_report_to_dashboard(dashboard_id, bookmark_id)` (clones the bookmark)
- Inline content action via `UpdateDashboardParams(content=...)` (preferred)

### 6.2 add_report_to_dashboard() CLONES the bookmark

This method creates a "Duplicate of ..." copy of the bookmark. The original bookmark is unchanged. The cloned report gets a new `content_id` on the dashboard. To avoid this:
- Use inline report creation (Section 2.3) instead
- Track the returned `Dashboard` to find the new content ID

### 6.3 Inline report creation is preferred

Use the `content_params.bookmark` pattern (Section 2.3) to create reports directly on the dashboard. Benefits:
- No separate bookmark entity created
- No "Duplicate of ..." name prefix
- No need to track cloned IDs
- Single API call

### 6.4 GET `order` vs PATCH `rows_order`

The layout returned by `get_dashboard()` uses `"order"` for the row ordering key. When sending a layout patch via `update_dashboard()`, the key must be `"rows_order"`. Using `"order"` in a patch will silently fail to reorder rows.

### 6.5 Never include `version` in layout PATCH

The layout from GET includes `"version": "2.0.0"`. Do **not** include this key in the PATCH payload. The API rejects layout patches that contain the `version` key.

### 6.6 Content IDs change on clone

When using `add_report_to_dashboard()` or the `source_bookmark_id` content action, the new report gets a new `content_id`. Always read the response to discover the real ID. Do not assume the content ID matches the source bookmark ID.

### 6.7 Strip newlines from text card markdown

Always call `.replace("\n", "")` on markdown strings before sending. Mixpanel's TipTap editor takes a markdown-it code path that mangles HTML when newlines are present. This produces garbled rendering in the dashboard UI.

```python
# WRONG -- newlines in the string
markdown = "<h2>Title</h2>\n<p>Description</p>"

# CORRECT -- no newlines
markdown = "<h2>Title</h2><p>Description</p>"

# CORRECT -- use Python string concatenation for readability
markdown = (
    "<h2>Title</h2>"
    "<p>Description</p>"
)
```

### 6.8 Character and length limits

| Constraint | Limit |
|---|---|
| Dashboard title | Max 255 characters |
| Dashboard description | Max 400 characters |
| Cell widths per row | Must sum to exactly 12 |
| Items per row | Max 4 |
| Rows per dashboard | Max 30 |
| Nested dashboard depth | Max 2 levels |

### 6.9 Cell widths must sum to 12

Standard width values are 3, 4, 6, and 12. Any combination is allowed as long as widths in a row sum to exactly 12. Examples:

| Layout | Widths |
|---|---|
| 4 equal cards | 3 + 3 + 3 + 3 = 12 |
| 3 equal cards | 4 + 4 + 4 = 12 |
| 2 equal cards | 6 + 6 = 12 |
| 1 full-width card | 12 |
| 1 wide + 1 narrow | 8 + 4 = 12 |
| 1 wide + 2 narrow | 6 + 3 + 3 = 12 |

### 6.10 Nested dashboards require feature flag

Nested dashboards (embedding one dashboard inside another) are limited to 2 levels deep and are gated behind a feature flag. Not all projects have this enabled.

### 6.11 The `markdown` field accepts only HTML

Despite being named `markdown`, the field accepts only HTML tags. Markdown syntax (`# Heading`, `**bold**`, `- list item`) is not parsed and will render as literal text.

---

## 7. Dashboard Lifecycle Methods

### 7.1 Duplicate a dashboard

```python
duplicate = ws.create_dashboard(CreateDashboardParams(
    title="Product Health (Copy)",
    duplicate=existing_dashboard_id,
))
```

This creates a complete copy including all reports, text cards, and layout. The new dashboard has its own ID and independent content IDs.

Cross-project duplication is also possible via the raw API by including `target_project_id` alongside `duplicate` in the POST body.

### 7.2 Favorite / unfavorite

```python
# Add to current user's favorites
ws.favorite_dashboard(dashboard_id)

# Remove from favorites
ws.unfavorite_dashboard(dashboard_id)
```

Favorites are per-user. They appear in the "Favorites" filter in the Mixpanel dashboard list.

### 7.3 Pin / unpin

```python
# Pin for all project members
ws.pin_dashboard(dashboard_id)

# Remove pin
ws.unpin_dashboard(dashboard_id)
```

Pinned dashboards appear at the top of the dashboard list for all project members. Use pinning for team-wide dashboards that everyone should see.

### 7.4 Full lifecycle example

```python
import mixpanel_headless as mp
from mixpanel_headless.types import CreateDashboardParams, UpdateDashboardParams
import json

ws = mp.Workspace()

# 1. Create
dashboard = ws.create_dashboard(CreateDashboardParams(
    title="Weekly Product Review",
    description="Key metrics reviewed in the weekly product sync.",
    time_filter={
        "dateRange": {"type": "in the last", "window": {"unit": "day", "value": 7}},
        "displayText": "Last 7 days"
    },
))

# 2. Add content
ws.update_dashboard(dashboard.id, UpdateDashboardParams(
    content={"action": "create", "content_type": "text",
             "content_params": {"markdown": "<h2>Weekly Product Review</h2><p>Updated every Monday.</p>"}}))

result = ws.query("Login", from_date="2025-01-01", to_date="2025-03-31")
ws.update_dashboard(dashboard.id, UpdateDashboardParams(
    content={"action": "create", "content_type": "report",
             "content_params": {"bookmark": {"name": "DAU Trend", "type": "insights",
                                              "params": json.dumps(result.params)}}}))

# 3. Arrange layout (read IDs first)
dash = ws.get_dashboard(dashboard.id)
# ... build layout patch from dash.layout ...

# 4. Pin for the team
ws.pin_dashboard(dashboard.id)

# 5. Later: update title
ws.update_dashboard(dashboard.id, UpdateDashboardParams(
    title="Weekly Product Review (Q2 2025)"
))

# 6. Cleanup: delete when no longer needed
ws.delete_dashboard(dashboard.id)
```

---

## 8. Update Operations

### 8.1 Operation Ordering

When making multiple changes to an existing dashboard, operations must execute in this order:

1. **Metadata** (title, description) — standalone PATCH
2. **Cell creates** — add new content first
3. **Row reorder** (`rows_order`) — after creates, so temp IDs can be resolved
4. **Cell updates** — modify existing content in place
5. **Cell deletes** — remove content
6. **Row deletes** — remove entire rows last

Wrong order causes failures: reordering before creating temp rows gives "unknown row ID"; deleting before creating can leave layout gaps.

Re-fetch the dashboard (`ws.get_dashboard()`) between layout-modifying operations to get updated row/cell IDs.

### 8.2 Combined Content + Layout PATCH

To add a cell to a **specific existing row** (not just append to the bottom), send both `content` and `layout` in the same `UpdateDashboardParams`:

```python
import copy

dash = ws.get_dashboard(dashboard_id)
layout = copy.deepcopy(dash.layout)
target_row = layout["rows"][target_row_id]

# Redistribute widths: 12 / (N+1) for all cells including new
new_count = len(target_row["cells"]) + 1
cell_width = 12 // new_count
for cell in target_row["cells"]:
    cell["width"] = cell_width
target_row["cells"].append({"temp_id": "-1", "width": cell_width})

ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "report",
        "content_params": {
            "bookmark": {
                "name": "New Report",
                "type": "insights",
                "params": json.dumps(result.params),
            }
        },
    },
    layout={
        "rows_order": layout["order"],
        "rows": layout["rows"],
    },
))
```

Without the `layout` field, new content always appends as a full-width row at the bottom.

### 8.3 Temp ID Resolution for New Rows

When adding content to a new row during an update:

1. Use a temp string ID for the new row (e.g., `"temp-row-1"`)
2. Execute the cell create — the new row appears in the dashboard response with a real ID
3. Diff row sets before/after to discover the real row ID
4. Use the real ID in subsequent `rows_order` operations

```python
before_rows = set(dash.layout["rows"].keys())
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={"action": "create", "content_type": "text",
             "content_params": {"markdown": "<h2>New Section</h2>"}},
))
dash = ws.get_dashboard(dashboard_id)
after_rows = set(dash.layout["rows"].keys())
new_row_id = (after_rows - before_rows).pop()
```

### 8.4 Cross-Type Cell Updates

The API rejects changing `content_type` on an update action (e.g., converting a text cell to a report cell). To achieve this:

1. Delete the existing cell
2. Create a new cell with the desired type

```python
# Delete old text card
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={"action": "delete", "content_type": "text", "content_id": old_text_id},
))
# Create new report in its place
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={"action": "create", "content_type": "report",
             "content_params": {"bookmark": {...}}},
))
```

### 8.5 Report-Link vs Report

Dashboard cells have two report content types:

| `content_type` | Ownership | Editable? |
|---|---|---|
| `"report"` | Owned by this dashboard | Yes — can update params, name, description |
| `"report-link"` | Linked from another dashboard | No — read-only reference |

When analyzing or modifying existing dashboards, check the `content_type` in layout cells. Attempting to update a report-link's params will fail. Use `update_report_link()` only to change the link type, not the underlying report.

---

## 9. Dashboard Analysis

### 9.1 Extracting Dashboard Structure

`get_dashboard()` returns a `Dashboard` with `layout` and `contents` fields. Parse them to understand what a dashboard contains:

```python
import json, re

dash = ws.get_dashboard(dashboard_id)
layout = dash.layout    # {"version": "2.0.0", "order": [...], "rows": {...}}
contents = dash.contents  # {"report": {...}, "text": {...}}

rows = []
for row_id in layout["order"]:
    row = layout["rows"][row_id]
    cells = []
    for cell in row["cells"]:
        cid = str(cell["content_id"])
        ctype = cell["content_type"]
        if ctype in ("report", "report-link"):
            info = contents["report"][cid]
            params = json.loads(info["params"]) if isinstance(info["params"], str) else (info.get("params") or {})
            cells.append({
                "type": ctype,
                "name": info.get("name", ""),
                "report_type": info.get("type", "insights"),
                "bookmark_id": info["id"],
                "description": info.get("description", ""),
                "width": cell["width"],
                "is_owned": ctype == "report",
                "params": params,
            })
        elif ctype == "text":
            md = contents["text"].get(cid, {}).get("markdown", "")
            cells.append({
                "type": "text",
                "markdown": md,
                "is_section_header": bool(re.search(r'<h2[\s>]', md, re.I)),
                "width": cell["width"],
            })
    rows.append({"row_id": row_id, "height": row.get("height", 0), "cells": cells})
```

### 9.2 Section Header Detection

Text cards with `<h2>` tags act as section dividers. Detect them with:

```python
is_section_header = bool(re.search(r'<h2[\s>]', markdown, re.I))
```

This lets you group reports by section, which is essential for:
- Understanding dashboard organization
- Responding to "add a report to the Retention section"
- Generating section-aware summaries

### 9.3 Executing Dashboard Reports

Execute each report to get live data as a DataFrame:

```python
for row in rows:
    for cell in row["cells"]:
        if cell["type"] not in ("report", "report-link"):
            continue
        bid = cell["bookmark_id"]
        btype = cell["report_type"]
        if btype == "flows":
            result = ws.query_saved_flows(bid)
        else:
            result = ws.query_saved_report(bid, bookmark_type=btype)
        df = result.df
        # Summarize based on type:
        # insights: df.describe(), trend = df.iloc[-1] vs df.iloc[-8]
        # funnels: step conversion rates from result.series
        # retention: day-N rates from result.series
```

### 9.4 Cross-Dashboard Analysis

When working with multiple dashboards, build a unified data model:

```python
import pandas as pd

dashboard_ids = [1001, 1002, 1003]
all_reports = {}

for did in dashboard_ids:
    dash = ws.get_dashboard(did)
    for cid, info in dash.contents.get("report", {}).items():
        bid, btype = info["id"], info["type"]
        try:
            if btype == "flows":
                result = ws.query_saved_flows(bid)
            else:
                result = ws.query_saved_report(bid, bookmark_type=btype)
            all_reports[f"{dash.title} / {info['name']}"] = result.df
        except Exception as e:
            print(f"Skipping {info['name']}: {e}")

# Join on date index for cross-metric correlation
# combined = pd.concat([df1, df2], axis=1)
# correlation = combined.corr()
```

Patterns to look for across dashboards:
- **Correlated metrics** — DAU trend aligns with feature adoption
- **Divergent signals** — signups up but retention down
- **Complementary data** — one dashboard's KPIs explained by another's funnels
- **Gaps** — metrics referenced in text cards but not visualized
