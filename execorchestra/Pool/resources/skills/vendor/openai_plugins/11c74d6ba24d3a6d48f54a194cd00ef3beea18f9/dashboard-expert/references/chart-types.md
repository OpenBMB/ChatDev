# Chart Type Selection Guide

Quick-lookup reference for choosing the right chart type per report type, with width recommendations for dashboard layout.

---

## 1. Decision Tree

| Question | Chart Type | `chartType` | `plotStyle` |
|---|---|---|---|
| Need a single headline number? | Metric | `insights-metric` | |
| Tracking something over time? | Line | `line` | |
| Comparing categories? | Bar | `bar` | |
| Showing composition over time? | Stacked Line | `line` | `stacked` |
| Showing composition across categories? | Stacked Bar | `bar` | `stacked` |
| Need detailed data? | Table | `table` | |
| Measuring conversion? | Funnel Steps | `funnel-steps` | |
| Measuring retention? | Retention Curve | `retention-curve` | |
| Exploring user paths? | Sankey | `sankey` | |

---

## 2. Insights Chart Types

| Chart Type | `chartType` | `plotStyle` | Best For | Width |
|---|---|---|---|---|
| Line | `line` | `standard` | Trends over time | 6 or 12 |
| Stacked Line | `line` | `stacked` | Composition trends over time | 12 |
| Bar | `bar` | `standard` | Categorical comparisons, rankings | 6 or 12 |
| Stacked Bar | `bar` | `stacked` | Composition across categories | 12 |
| Column | `column` | `standard` | Vertical bar, fewer categories | 6 or 12 |
| Stacked Column | `column` | `stacked` | Composition across categories (vertical) | 12 |
| Pie | `pie` | | Share/proportion (max 6 segments) | 6 |
| Table | `table` | | Multi-dimensional detailed data | 12 |
| Metric | `insights-metric` | | Single KPI headline number | 3 or 4 |

### How Stacking Works

Stacked charts are NOT separate chart types. They use the base `chartType` (`line`, `bar`, or `column`) with `plotStyle` set to `"stacked"` in `displayOptions`:

```json
"displayOptions": {
  "chartType": "bar",
  "plotStyle": "stacked"
}
```

**NEVER use** `bar-stacked`, `stacked-line`, or `stacked-column` as `chartType` values — these are display-layer labels used by the Mixpanel frontend, not valid API values. The API will reject them.

Valid `chartType` values: `line`, `bar`, `column`, `pie`, `table`, `insights-metric`, `funnel-steps`, `funnel-top-paths`, `retention-curve`, `frequency-curve`

Valid `plotStyle` values: `standard` (default), `stacked`

### When to Use / When NOT to Use

- **Line** -- Use for time series with continuous data. Not for categorical comparisons or single data points.
- **Bar** -- Use for ranking or comparing discrete categories. Not for time series (use line instead).
- **Stacked Bar/Line/Column** -- Use to show part-to-whole composition. Set `chartType` to the base type and `plotStyle` to `"stacked"`. Not when individual values matter more than composition.
- **Column** -- Use like bar but vertical; better with fewer categories. Not for many categories (labels overlap).
- **Pie** -- Use for simple share breakdowns with 2-6 segments. Not for more than 6 segments or precise comparisons.
- **Table** -- Use when exact values or multiple dimensions are needed. Not for quick visual scanning.
- **Metric** -- Use for a single KPI number (DAU, revenue, conversion rate). Not for trends or comparisons.

---

## 3. Funnel Chart Types

| Chart Type | Slug | Best For | Width |
|---|---|---|---|
| Steps | `funnel-steps` | Standard funnel visualization | 12 (3+ steps), 6 (2 steps) |
| Trend | `funnel-trend` | Conversion rate over time | 6 or 12 |
| Top Paths | `funnel-top-paths` | Alternative paths through funnel | 12 |
| Frequency Line | `funnel-frequency-line` | How often users convert | 6 |
| Frequency Bar | `funnel-frequency-bar` | Conversion frequency distribution | 6 |
| Time to Convert (Line) | `funnel-ttc-line` | Duration analysis | 6 or 12 |
| Time to Convert (Bar) | `funnel-ttc-bar` | Duration distribution | 6 |
| Median TTC | `funnel-median-ttc` | Central tendency of conversion time | 6 |

---

## 4. Retention Chart Types

| Chart Type | Slug | Best For | Width |
|---|---|---|---|
| Curve | `retention-curve` | Classic retention decay curve | 12 |
| Table | `retention-table` | Cohort-by-cohort retention grid | 12 |
| Trend | `retention-trend` | Retention rate over time | 6 or 12 |
| Trend Metric | `retention-trend-metric` | Single retention rate number | 3 or 4 |
| Line | `line-retention` | Retention as line chart | 6 or 12 |

---

## 5. Flows Chart Types

| Chart Type | Slug | Best For | Width |
|---|---|---|---|
| Sankey | `sankey` | User journey visualization | 12 |
| Paths | `paths` | Path frequency analysis | 12 |

---

## 6. Math Types

| Math | Slug | Requires Property | Description |
|---|---|---|---|
| Total | `total` | No | Count of events |
| Unique | `unique` | No | Count of unique users |
| DAU | `dau` | No | Daily active users |
| WAU | `wau` | No | Weekly active users |
| MAU | `mau` | No | Monthly active users |
| Sum | `total` | Yes (numeric) | Sum of property values |
| Average | `average` | Yes (numeric) | Average property value |
| Median | `median` | Yes (numeric) | Median property value |
| Min | `min` | Yes (numeric) | Minimum property value |
| Max | `max` | Yes (numeric) | Maximum property value |
| P25 | `p25` | Yes (numeric) | 25th percentile |
| P75 | `p75` | Yes (numeric) | 75th percentile |
| P90 | `p90` | Yes (numeric) | 90th percentile |
| P99 | `p99` | Yes (numeric) | 99th percentile |

### Common Invalid Aliases

| Wrong | Correct | Note |
|---|---|---|
| `sum` | `total` (with property) | "sum" is not a valid math type |
| `count` | `total` | Use `total` without a property |
| `distinct` | `unique` | |
| `avg` | `average` | |
| `mean` | `average` | |

---

## 7. Width Recommendations

| Chart Type | Width | Layout Pattern |
|---|---|---|
| `insights-metric` | 3 or 4 | Pack 3-4 KPIs per row |
| `line` | 6 or 12 | 6 for paired comparison, 12 for detail |
| `line` + stacked | 12 | Composition needs space |
| `bar` | 6 or 12 | 6 for paired, 12 for many categories |
| `bar` + stacked | 12 | Needs full width for stacked segments |
| `column` | 6 or 12 | Same as bar |
| `column` + stacked | 12 | Composition needs space |
| `pie` | 6 | Pair with related chart |
| `table` | 12 | Always full width |
| `funnel-steps` | 12 | Complex funnels need space |
| `funnel-trend` | 6 or 12 | 6 for paired, 12 for standalone |
| `funnel-top-paths` | 12 | Path detail needs space |
| `retention-curve` | 12 | Full width for readability |
| `retention-table` | 12 | Full width for cohort grid |
| `retention-trend` | 6 or 12 | 6 for paired, 12 for standalone |
| `retention-trend-metric` | 3 or 4 | Same as insights-metric |
| `sankey` | 12 | Always full width |
| `paths` | 12 | Always full width |

---

## 8. Setting Chart Type

Chart type is set in `displayOptions.chartType` within the bookmark params JSON. When using typed query methods, the chart type is set automatically.

```python
import json

# Typed queries set chartType automatically -- no override needed
result = ws.query("Login", from_date="2025-01-01", to_date="2025-03-31")

# The chart type lives at params["displayOptions"]["chartType"]
# To inspect:
params = result.params
chart_type = params.get("displayOptions", {}).get("chartType")

# When creating inline reports, the params carry the chart type through:
ws.update_dashboard(dashboard_id, UpdateDashboardParams(
    content={
        "action": "create",
        "content_type": "report",
        "content_params": {
            "bookmark": {
                "name": "DAU Trend",
                "type": "insights",
                "params": json.dumps(result.params),
            }
        },
    }
))
```
