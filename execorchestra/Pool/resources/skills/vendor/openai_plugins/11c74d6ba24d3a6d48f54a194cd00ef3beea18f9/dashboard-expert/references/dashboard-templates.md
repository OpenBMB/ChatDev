# Dashboard Design Templates

9 purpose-built dashboard templates for common analytics use cases. Each template specifies a complete row-by-row layout, text card content, chart types, and placeholder events that an agent adapts to the user's actual schema.

---

## How to Use These Templates

### Adaptation Workflow

1. **Pick a template** that matches the user's goal (or combine sections from multiple templates).
2. **Discover the schema** -- run `ws.events()` and `ws.properties(event=...)` to find real event names.
3. **Map placeholders to real events** -- replace `{signup_event}`, `{login_event}`, etc. with actual event names from the project. Drop any section whose placeholder events have zero volume.
4. **Validate data** -- query each event before building a report. Skip reports that would render as empty charts.
5. **Adapt row count** -- remove sections that don't apply, or add sections for project-specific needs. Stay within the 30-row dashboard limit.
6. **Build** -- follow the Build mode workflow in `SKILL.md`, using the template layout as the Phase B2 plan.

### Layout Conventions

| Symbol | Meaning |
|---|---|
| `w=N` | Cell width (columns out of 12). Widths in a row must sum to 12. |
| `h=N` | Row height in pixels. `h=0` means auto-height (text-only rows). |
| `insights-metric` | Big-number KPI card (single value with comparison). |
| `line` | Time-series line chart. |
| `bar` | Categorical bar chart. |
| `table` | Data table with sortable columns. |
| `line` + `plotStyle: stacked` | Stacked area/line chart for composition over time. |
| `funnel-steps` | Funnel visualization showing step-by-step conversion. |
| `retention-curve` | Retention curve or cohort grid. |
| `sankey` | Sankey/flow diagram showing user paths. |

### Placeholder Event Conventions

Templates use curly-brace placeholders for event names. The agent replaces these with real events discovered from the project schema.

| Placeholder | Typical Matches |
|---|---|
| `{signup_event}` | Sign Up, Create Account, Registration Complete |
| `{login_event}` | Login, Sign In, Session Start |
| `{core_action_event}` | The primary value-delivery action (e.g., Send Message, Create Post, Place Order) |
| `{purchase_event}` | Purchase, Order Completed, Subscription Started |
| `{feature_event}` | The specific feature being tracked (agent fills in) |
| `{error_event}` | Error, Exception, Crash, API Error |
| `{page_view_event}` | Page Viewed, Screen View, $mp_web_page_view |
| `{referral_event}` | Invite Sent, Referral Created, Share |
| `{onboarding_step_N}` | Sequential onboarding steps (agent discovers from schema) |

---

## Template 1: KPI Dashboard

**Description:** Executive overview of key business metrics with trend lines and core funnels.

**Use case:** Weekly standups, board meetings, investor updates, team-wide visibility into product health.

**Audience:** Leadership, founders, board members, cross-functional stakeholders.

**Placeholder events:** `{signup_event}`, `{login_event}`, `{core_action_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: DAU | w=3 | h=336 | insights-metric |
| 2 | KPI: WAU | w=3 | h=336 | insights-metric |
| 2 | KPI: MAU | w=3 | h=336 | insights-metric |
| 2 | KPI: New Signups | w=3 | h=336 | insights-metric |
| 3 | Section header: Growth Trends | w=12 | h=0 | text |
| 4 | DAU trend (90d) | w=6 | h=418 | line |
| 4 | New signups trend (90d) | w=6 | h=418 | line |
| 5 | Section header: Conversion | w=12 | h=0 | text |
| 6 | Signup-to-activation funnel | w=12 | h=588 | funnel-steps |
| 7 | Section header: Retention | w=12 | h=0 | text |
| 8 | New user retention curve | w=12 | h=500 | retention-curve |
| 9 | Section header: Engagement | w=12 | h=0 | text |
| 10 | Sessions per user (bar) | w=6 | h=418 | bar |
| 10 | Top events by volume (table) | w=6 | h=418 | table |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>Key Performance Indicators</h2><p>Headline metrics for {product_name}. All reports use a rolling 90-day window unless noted.</p>
```

**Row 3 -- Growth Trends:**
```
<h2>Growth Trends</h2><p>User acquisition and daily engagement over time.</p>
```

**Row 5 -- Conversion:**
```
<h2>Conversion</h2><p>How effectively new visitors become activated users.</p>
```

**Row 7 -- Retention:**
```
<h2>Retention</h2><p>How well the product brings users back after their first visit.</p>
```

**Row 9 -- Engagement:**
```
<h2>Engagement</h2><p>Depth of product usage across active users.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| DAU | `{login_event}` | `dau` | -- | Compare to previous period |
| WAU | `{login_event}` | `wau` | -- | Compare to previous period |
| MAU | `{login_event}` | `mau` | -- | Compare to previous period |
| New Signups | `{signup_event}` | `total` | -- | Compare to previous period |
| DAU trend | `{login_event}` | `dau` | -- | Line chart, 90 days |
| Signups trend | `{signup_event}` | `total` | -- | Line chart, 90 days |
| Signup funnel | `{signup_event}` > `{login_event}` > `{core_action_event}` | -- | -- | 3-step funnel |
| Retention curve | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | 12-week retention |
| Sessions/user | `{login_event}` | `avg_count_per_user` | -- | Bar chart by week |
| Top events | Top 10 events | `total` | -- | Table, sorted by volume |

---

## Template 2: Feature Launch Dashboard

**Description:** Track adoption, engagement, and retention impact of a newly launched feature.

**Use case:** Post-launch monitoring during the first 30-90 days of a feature release.

**Audience:** Product managers, engineering leads, designers who built the feature.

**Placeholder events:** `{feature_event}`, `{login_event}`, `{core_action_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: Adoption Rate | w=4 | h=336 | insights-metric |
| 2 | KPI: Feature DAU | w=4 | h=336 | insights-metric |
| 2 | KPI: Avg Uses per User | w=4 | h=336 | insights-metric |
| 3 | Section header: Adoption Trend | w=12 | h=0 | text |
| 4 | Feature adoption over time | w=12 | h=500 | line |
| 5 | Section header: Discovery and Activation | w=12 | h=0 | text |
| 6 | Discovery-to-use funnel | w=6 | h=418 | funnel-steps |
| 6 | Time to first use (bar) | w=6 | h=418 | bar |
| 7 | Section header: Engagement Depth | w=12 | h=0 | text |
| 8 | Feature frequency distribution | w=6 | h=418 | bar |
| 8 | Feature usage by segment | w=6 | h=418 | bar |
| 9 | Section header: Retention Impact | w=12 | h=0 | text |
| 10 | Feature-user retention | w=6 | h=418 | retention-curve |
| 10 | Non-feature-user retention | w=6 | h=418 | retention-curve |
| 11 | Section header: User Flows | w=12 | h=0 | text |
| 12 | Post-feature user flow | w=12 | h=588 | sankey |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>Feature Launch: {feature_name}</h2><p>Tracking adoption, engagement, and retention impact since {launch_date}.</p>
```

**Row 3 -- Adoption Trend:**
```
<h2>Adoption Trend</h2><p>Cumulative and daily adoption since launch.</p>
```

**Row 5 -- Discovery and Activation:**
```
<h2>Discovery and Activation</h2><p>How users find and first engage with the feature.</p>
```

**Row 7 -- Engagement Depth:**
```
<h2>Engagement Depth</h2><p>How often and how deeply users engage with the feature.</p>
```

**Row 9 -- Retention Impact:**
```
<h2>Retention Impact</h2><p>Comparing retention between feature adopters and non-adopters.</p>
```

**Row 11 -- User Flows:**
```
<h2>User Flows</h2><p>What users do immediately after using the feature.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| Adoption Rate | `{feature_event}` / `{login_event}` | `dau` ratio | -- | Percentage of DAU using feature |
| Feature DAU | `{feature_event}` | `dau` | -- | Compare to previous period |
| Avg Uses/User | `{feature_event}` | `avg_count_per_user` | -- | Compare to previous period |
| Adoption over time | `{feature_event}` | `dau` | -- | Line chart since launch |
| Discovery funnel | `{page_view_event}` > `{feature_event}` | -- | -- | 2-step funnel |
| Time to first use | `{feature_event}` | `total` | Time since signup bucket | Bar chart |
| Frequency dist. | `{feature_event}` | `total` | Uses per user bucket | Bar chart |
| Usage by segment | `{feature_event}` | `total` | Platform or user tier | Bar chart |
| Feature-user retention | Born: `{feature_event}`, Return: `{login_event}` | -- | -- | 8-week retention |
| Non-feature retention | Born: `{login_event}` (excl. feature), Return: `{login_event}` | -- | -- | 8-week retention |
| Post-feature flow | Start: `{feature_event}` | -- | -- | Sankey, top 5 next events |

---

## Template 3: AARRR / Pirate Metrics Dashboard

**Description:** Full-funnel product health tracking across the five AARRR stages: Acquisition, Activation, Retention, Revenue, and Referral.

**Use case:** Comprehensive growth health check; identifying which funnel stage needs the most attention.

**Audience:** Growth teams, product leadership, startup founders.

**Placeholder events:** `{signup_event}`, `{login_event}`, `{core_action_event}`, `{purchase_event}`, `{referral_event}`, `{onboarding_step_1}`, `{onboarding_step_2}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | Section header: Acquisition | w=12 | h=0 | text |
| 3 | KPI: New Users (total) | w=4 | h=336 | insights-metric |
| 3 | KPI: Signup Rate | w=4 | h=336 | insights-metric |
| 3 | KPI: Top Channel | w=4 | h=336 | insights-metric |
| 4 | New signups trend | w=6 | h=418 | line |
| 4 | Signups by channel | w=6 | h=418 | bar |
| 5 | Section header: Activation | w=12 | h=0 | text |
| 6 | KPI: Activation Rate | w=4 | h=336 | insights-metric |
| 6 | KPI: Time to Activate | w=4 | h=336 | insights-metric |
| 6 | KPI: Onboarding Completion | w=4 | h=336 | insights-metric |
| 7 | Activation funnel | w=12 | h=588 | funnel-steps |
| 8 | Section header: Retention | w=12 | h=0 | text |
| 9 | KPI: D1 Retention | w=4 | h=336 | insights-metric |
| 9 | KPI: D7 Retention | w=4 | h=336 | insights-metric |
| 9 | KPI: D30 Retention | w=4 | h=336 | insights-metric |
| 10 | Retention curve | w=12 | h=500 | retention-curve |
| 11 | Section header: Revenue | w=12 | h=0 | text |
| 12 | KPI: Revenue (total) | w=4 | h=336 | insights-metric |
| 12 | KPI: ARPU | w=4 | h=336 | insights-metric |
| 12 | KPI: Paid Conversion | w=4 | h=336 | insights-metric |
| 13 | ARPU trend | w=6 | h=418 | line |
| 13 | Conversion to paid funnel | w=6 | h=418 | funnel-steps |
| 14 | Section header: Referral | w=12 | h=0 | text |
| 15 | KPI: Referral Rate | w=4 | h=336 | insights-metric |
| 15 | KPI: Viral Coefficient | w=4 | h=336 | insights-metric |
| 15 | KPI: Referred Signups | w=4 | h=336 | insights-metric |
| 16 | Referral trend | w=6 | h=418 | line |
| 16 | Referral funnel | w=6 | h=418 | funnel-steps |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>AARRR Pirate Metrics</h2><p>Full-funnel health across Acquisition, Activation, Retention, Revenue, and Referral.</p>
```

**Row 2 -- Acquisition:**
```
<h2>Acquisition</h2><p>How effectively the product attracts new users.</p>
```

**Row 5 -- Activation:**
```
<h2>Activation</h2><p>How quickly new users reach their first moment of value.</p>
```

**Row 8 -- Retention:**
```
<h2>Retention</h2><p>How well the product brings users back after signup.</p>
```

**Row 11 -- Revenue:**
```
<h2>Revenue</h2><p>Monetization health and conversion to paid.</p>
```

**Row 14 -- Referral:**
```
<h2>Referral</h2><p>Organic growth through user-driven sharing and invites.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| New Users | `{signup_event}` | `total` | -- | Compare to previous period |
| Signup Rate | `{signup_event}` / `{page_view_event}` | ratio | -- | Visitor-to-signup conversion |
| Top Channel | `{signup_event}` | `total` | UTM source | Show top value |
| Signups trend | `{signup_event}` | `total` | -- | Line chart, 90 days |
| Signups by channel | `{signup_event}` | `total` | UTM source | Bar chart, top 5 |
| Activation Rate | `{core_action_event}` / `{signup_event}` | ratio | -- | Within first 7 days |
| Time to Activate | `{core_action_event}` | `median_time` | -- | Median time from signup |
| Onboarding Completion | `{onboarding_step_2}` / `{onboarding_step_1}` | ratio | -- | Completion rate |
| Activation funnel | `{signup_event}` > `{onboarding_step_1}` > `{core_action_event}` | -- | -- | 3-step funnel |
| D1 Retention | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | Day 1 value |
| D7 Retention | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | Day 7 value |
| D30 Retention | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | Day 30 value |
| Retention curve | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | 12-week curve |
| Revenue | `{purchase_event}` | `sum` of revenue property | -- | Compare to previous period |
| ARPU | `{purchase_event}` | `avg` of revenue property | -- | Per-user average |
| Paid Conversion | `{purchase_event}` / `{signup_event}` | ratio | -- | Overall conversion |
| ARPU trend | `{purchase_event}` | `avg` of revenue property | -- | Line chart, 90 days |
| Paid funnel | `{signup_event}` > `{core_action_event}` > `{purchase_event}` | -- | -- | 3-step funnel |
| Referral Rate | `{referral_event}` / `{login_event}` | ratio | -- | % of users who refer |
| Viral Coefficient | `{referral_event}` | `avg_count_per_user` | -- | Invites per user |
| Referred Signups | `{signup_event}` | `total` | Referral source | Filter to referred |
| Referral trend | `{referral_event}` | `total` | -- | Line chart, 90 days |
| Referral funnel | `{referral_event}` > `{signup_event}` (referred) | -- | -- | 2-step funnel |

---

## Template 4: Conversion Funnel Dashboard

**Description:** Deep dive into a specific conversion funnel with step-by-step drop-off analysis, segment comparisons, and trend tracking.

**Use case:** Optimizing a critical multi-step conversion flow (signup, checkout, onboarding).

**Audience:** Growth, marketing, product managers focused on conversion optimization.

**Placeholder events:** `{funnel_step_1}`, `{funnel_step_2}`, `{funnel_step_3}`, `{funnel_step_4}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: Overall Conversion | w=4 | h=336 | insights-metric |
| 2 | KPI: Median Time to Convert | w=4 | h=336 | insights-metric |
| 2 | KPI: Daily Conversions | w=4 | h=336 | insights-metric |
| 3 | Section header: Full Funnel | w=12 | h=0 | text |
| 4 | Complete funnel visualization | w=12 | h=588 | funnel-steps |
| 5 | Section header: Step-by-Step Drop-off | w=12 | h=0 | text |
| 6 | Step 1 > 2 conversion | w=4 | h=336 | insights-metric |
| 6 | Step 2 > 3 conversion | w=4 | h=336 | insights-metric |
| 6 | Step 3 > 4 conversion | w=4 | h=336 | insights-metric |
| 7 | Section header: Segment Comparison | w=12 | h=0 | text |
| 8 | Funnel by platform | w=6 | h=418 | bar |
| 8 | Funnel by source | w=6 | h=418 | bar |
| 9 | Section header: Funnel Trend | w=12 | h=0 | text |
| 10 | Conversion rate over time | w=12 | h=500 | line |
| 11 | Section header: Drop-off Analysis | w=12 | h=0 | text |
| 12 | Post-drop-off user flow | w=12 | h=588 | sankey |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>{funnel_name} Funnel Analysis</h2><p>Deep dive into conversion performance across {step_count} steps. Identify where users drop off and which segments convert best.</p>
```

**Row 3 -- Full Funnel:**
```
<h2>Full Funnel</h2><p>End-to-end conversion from {funnel_step_1} to {funnel_step_4}.</p>
```

**Row 5 -- Step-by-Step Drop-off:**
```
<h2>Step-by-Step Drop-off</h2><p>Conversion rate between each consecutive pair of steps.</p>
```

**Row 7 -- Segment Comparison:**
```
<h2>Segment Comparison</h2><p>How conversion varies across user segments.</p>
```

**Row 9 -- Funnel Trend:**
```
<h2>Funnel Trend</h2><p>Overall conversion rate tracked over time to spot regressions.</p>
```

**Row 11 -- Drop-off Analysis:**
```
<h2>Drop-off Analysis</h2><p>Where non-converters go after abandoning the funnel.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| Overall Conversion | `{funnel_step_1}` > ... > `{funnel_step_4}` | overall rate | -- | Compare to previous period |
| Median Time | `{funnel_step_1}` > `{funnel_step_4}` | `median_time` | -- | Time to complete funnel |
| Daily Conversions | `{funnel_step_4}` | `total` | -- | Completed conversions/day |
| Full funnel | `{funnel_step_1}` > `{funnel_step_2}` > `{funnel_step_3}` > `{funnel_step_4}` | -- | -- | Full funnel chart |
| Step 1>2 rate | `{funnel_step_1}` > `{funnel_step_2}` | step rate | -- | Pairwise conversion |
| Step 2>3 rate | `{funnel_step_2}` > `{funnel_step_3}` | step rate | -- | Pairwise conversion |
| Step 3>4 rate | `{funnel_step_3}` > `{funnel_step_4}` | step rate | -- | Pairwise conversion |
| By platform | `{funnel_step_1}` > ... > `{funnel_step_4}` | overall rate | Platform | Bar chart |
| By source | `{funnel_step_1}` > ... > `{funnel_step_4}` | overall rate | UTM source | Bar chart |
| Rate over time | `{funnel_step_1}` > ... > `{funnel_step_4}` | overall rate | -- | Line chart, 90 days |
| Drop-off flow | Start: users who did `{funnel_step_1}` but not `{funnel_step_4}` | -- | -- | Sankey of next actions |

---

## Template 5: Retention Dashboard

**Description:** Comprehensive analysis of user retention patterns with cohort breakdowns and engagement correlations.

**Use case:** Understanding why users churn and what behaviors predict long-term retention.

**Audience:** Product, growth, customer success teams.

**Placeholder events:** `{signup_event}`, `{login_event}`, `{core_action_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: D1 Retention | w=4 | h=336 | insights-metric |
| 2 | KPI: D7 Retention | w=4 | h=336 | insights-metric |
| 2 | KPI: D30 Retention | w=4 | h=336 | insights-metric |
| 3 | Section header: Retention Curve | w=12 | h=0 | text |
| 4 | Overall retention curve | w=12 | h=500 | retention-curve |
| 5 | Section header: Cohort Analysis | w=12 | h=0 | text |
| 6 | Retention by signup cohort (table) | w=12 | h=588 | table |
| 7 | Section header: Segment Comparison | w=12 | h=0 | text |
| 8 | Retention by platform | w=6 | h=418 | retention-curve |
| 8 | Retention by acquisition source | w=6 | h=418 | retention-curve |
| 9 | Section header: Return Drivers | w=12 | h=0 | text |
| 10 | Top return events | w=12 | h=500 | bar |
| 11 | Section header: Engagement Correlation | w=12 | h=0 | text |
| 12 | First-week actions vs D30 retention | w=6 | h=418 | bar |
| 12 | Feature usage vs D30 retention | w=6 | h=418 | bar |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>Retention Analysis</h2><p>Understanding user retention patterns, cohort performance, and engagement behaviors that predict long-term retention.</p>
```

**Row 3 -- Retention Curve:**
```
<h2>Retention Curve</h2><p>Percentage of users returning on each day after signup.</p>
```

**Row 5 -- Cohort Analysis:**
```
<h2>Cohort Analysis</h2><p>Weekly signup cohorts showing how retention evolves over time.</p>
```

**Row 7 -- Segment Comparison:**
```
<h2>Segment Comparison</h2><p>Retention differences across key user segments.</p>
```

**Row 9 -- Return Drivers:**
```
<h2>Return Drivers</h2><p>Which events most commonly bring users back to the product.</p>
```

**Row 11 -- Engagement Correlation:**
```
<h2>Engagement Correlation</h2><p>Behaviors in the first week that predict long-term retention.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| D1 Retention | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | Day 1 value, compare to previous |
| D7 Retention | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | Day 7 value, compare to previous |
| D30 Retention | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | Day 30 value, compare to previous |
| Overall curve | Born: `{signup_event}`, Return: `{login_event}` | -- | -- | 12-week retention curve |
| Cohort table | Born: `{signup_event}`, Return: `{login_event}` | -- | Signup week | Cohort grid table |
| By platform | Born: `{signup_event}`, Return: `{login_event}` | -- | Platform | Side-by-side curves |
| By source | Born: `{signup_event}`, Return: `{login_event}` | -- | UTM source | Side-by-side curves |
| Top return events | All events | `total` | Event name | Bar chart, users who returned D7+ |
| First-week actions | `{core_action_event}` count in week 1 | -- | Action count bucket | Bar showing D30 rate per bucket |
| Feature vs retention | `{feature_event}` usage in week 1 | -- | Used/not used | Bar showing D30 rate per group |

---

## Template 6: User Engagement Dashboard

**Description:** Measure the depth and breadth of product usage across daily patterns, feature adoption, and session analysis.

**Use case:** Understanding how deeply users engage, identifying power-user behaviors, and finding underused features.

**Audience:** Product managers, designers, user researchers.

**Placeholder events:** `{login_event}`, `{core_action_event}`, `{feature_event}`, `{page_view_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: DAU | w=3 | h=336 | insights-metric |
| 2 | KPI: Sessions per User | w=3 | h=336 | insights-metric |
| 2 | KPI: Avg Session Length | w=3 | h=336 | insights-metric |
| 2 | KPI: Feature Breadth | w=3 | h=336 | insights-metric |
| 3 | Section header: Usage Patterns | w=12 | h=0 | text |
| 4 | DAU by day of week | w=6 | h=418 | bar |
| 4 | DAU by hour of day | w=6 | h=418 | bar |
| 5 | Section header: Feature Usage | w=12 | h=0 | text |
| 6 | Feature usage ranking (table) | w=12 | h=588 | table |
| 7 | Section header: User Segments | w=12 | h=0 | text |
| 8 | Power users vs casual (actions/user) | w=6 | h=418 | bar |
| 8 | User engagement tiers | w=6 | h=418 | bar |
| 9 | Section header: Session Analysis | w=12 | h=0 | text |
| 10 | Session duration trend | w=12 | h=500 | line |
| 11 | Section header: User Flows | w=12 | h=0 | text |
| 12 | Top user paths | w=12 | h=588 | sankey |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>User Engagement</h2><p>Depth and breadth of product usage. Identifying power-user behaviors and underused features.</p>
```

**Row 3 -- Usage Patterns:**
```
<h2>Usage Patterns</h2><p>When users are most active during the week and day.</p>
```

**Row 5 -- Feature Usage:**
```
<h2>Feature Usage</h2><p>Which features are most and least used across the product.</p>
```

**Row 7 -- User Segments:**
```
<h2>User Segments</h2><p>Engagement distribution across user tiers.</p>
```

**Row 9 -- Session Analysis:**
```
<h2>Session Analysis</h2><p>How session depth changes over time.</p>
```

**Row 11 -- User Flows:**
```
<h2>User Flows</h2><p>Most common paths users take through the product.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| DAU | `{login_event}` | `dau` | -- | Compare to previous period |
| Sessions/User | `{login_event}` | `avg_count_per_user` | -- | Compare to previous period |
| Avg Session Length | `{page_view_event}` | `avg` of session duration | -- | In minutes |
| Feature Breadth | Distinct events per user | `unique` | -- | Avg distinct features used |
| By day of week | `{login_event}` | `dau` | Day of week | Bar chart |
| By hour of day | `{login_event}` | `total` | Hour of day | Bar chart |
| Feature ranking | Top 20 events | `total` + `dau` | Event name | Table, sorted by volume |
| Power vs casual | `{core_action_event}` | `total` | Actions per user bucket | Bar chart |
| Engagement tiers | `{login_event}` | `total` | Sessions per user bucket | Bar chart |
| Session duration | `{page_view_event}` | `median` of session duration | -- | Line chart, 90 days |
| User paths | Start: `{login_event}` | -- | -- | Sankey, top 5 paths |

---

## Template 7: Marketing Performance Dashboard

**Description:** Track acquisition channel effectiveness with channel-level trends, funnel comparisons, and retention by source.

**Use case:** Evaluating marketing spend, channel ROI, and campaign performance.

**Audience:** Marketing, growth, paid acquisition teams.

**Placeholder events:** `{signup_event}`, `{login_event}`, `{core_action_event}`, `{purchase_event}`, `{page_view_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: Total Signups | w=3 | h=336 | insights-metric |
| 2 | KPI: Signup Rate | w=3 | h=336 | insights-metric |
| 2 | KPI: Best Channel | w=3 | h=336 | insights-metric |
| 2 | KPI: Avg Conversion Rate | w=3 | h=336 | insights-metric |
| 3 | Section header: Channel Trends | w=12 | h=0 | text |
| 4 | Signups by channel over time | w=12 | h=500 | line (plotStyle: stacked) |
| 5 | Section header: Channel Quality | w=12 | h=0 | text |
| 6 | Channel conversion funnel | w=12 | h=588 | funnel-steps |
| 7 | Section header: Channel Retention | w=12 | h=0 | text |
| 8 | Retention by acquisition source | w=12 | h=500 | retention-curve |
| 9 | Section header: Campaign Performance | w=12 | h=0 | text |
| 10 | Campaign performance table | w=12 | h=588 | table |
| 11 | Section header: Attribution | w=12 | h=0 | text |
| 12 | First-touch attribution | w=6 | h=418 | bar |
| 12 | Last-touch attribution | w=6 | h=418 | bar |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>Marketing Performance</h2><p>Acquisition channel effectiveness, campaign ROI, and channel-level quality metrics.</p>
```

**Row 3 -- Channel Trends:**
```
<h2>Channel Trends</h2><p>Volume of signups by acquisition channel over time.</p>
```

**Row 5 -- Channel Quality:**
```
<h2>Channel Quality</h2><p>Funnel conversion rates compared across channels.</p>
```

**Row 7 -- Channel Retention:**
```
<h2>Channel Retention</h2><p>Which channels produce the most retained users.</p>
```

**Row 9 -- Campaign Performance:**
```
<h2>Campaign Performance</h2><p>Individual campaign metrics ranked by volume and conversion.</p>
```

**Row 11 -- Attribution:**
```
<h2>Attribution</h2><p>First-touch vs last-touch attribution of conversions by source.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| Total Signups | `{signup_event}` | `total` | -- | Compare to previous period |
| Signup Rate | `{signup_event}` / `{page_view_event}` | ratio | -- | Visitor-to-signup |
| Best Channel | `{signup_event}` | `total` | UTM source | Show top value |
| Avg Conversion | `{signup_event}` > `{core_action_event}` | overall rate | -- | Compare to previous period |
| By channel over time | `{signup_event}` | `total` | UTM source | Stacked line, 90 days |
| Channel funnel | `{signup_event}` > `{core_action_event}` > `{purchase_event}` | -- | UTM source | Funnel segmented by channel |
| Retention by source | Born: `{signup_event}`, Return: `{login_event}` | -- | UTM source | 8-week curves by channel |
| Campaign table | `{signup_event}` | `total`, `dau` | UTM campaign | Table sorted by volume |
| First-touch attr. | `{purchase_event}` | `total` | First-touch UTM source | Bar chart |
| Last-touch attr. | `{purchase_event}` | `total` | Last-touch UTM source | Bar chart |

---

## Template 8: Experiment Results Dashboard

**Description:** Present A/B test results with primary and secondary metric comparisons, segment breakdowns, and funnel/retention impact.

**Use case:** Reviewing experiment outcomes, making ship/kill decisions, presenting results to stakeholders.

**Audience:** Product managers, engineering leads, data scientists.

**Placeholder events:** `{primary_metric_event}`, `{secondary_metric_event}`, `{login_event}`, `{signup_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: Primary Metric Lift | w=4 | h=336 | insights-metric |
| 2 | KPI: Statistical Significance | w=4 | h=336 | insights-metric |
| 2 | KPI: Sample Size | w=4 | h=336 | insights-metric |
| 3 | Section header: Primary Metric | w=12 | h=0 | text |
| 4 | Primary metric: control vs variant | w=12 | h=500 | line |
| 5 | Section header: Secondary Metrics | w=12 | h=0 | text |
| 6 | Secondary metric A by group | w=6 | h=418 | bar |
| 6 | Secondary metric B by group | w=6 | h=418 | bar |
| 7 | Section header: Segment Breakdown | w=12 | h=0 | text |
| 8 | Results by segment (table) | w=12 | h=588 | table |
| 9 | Section header: Funnel Impact | w=12 | h=0 | text |
| 10 | Funnel by experiment group | w=12 | h=588 | funnel-steps |
| 11 | Section header: Retention Impact | w=12 | h=0 | text |
| 12 | Retention: control group | w=6 | h=418 | retention-curve |
| 12 | Retention: variant group | w=6 | h=418 | retention-curve |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>Experiment: {experiment_name}</h2><p><strong>Hypothesis:</strong> {hypothesis}. Running from {start_date} to {end_date}. Groups: Control ({control_pct}%) vs {variant_name} ({variant_pct}%).</p>
```

**Row 3 -- Primary Metric:**
```
<h2>Primary Metric</h2><p>Tracking {primary_metric_name} across experiment groups over time.</p>
```

**Row 5 -- Secondary Metrics:**
```
<h2>Secondary Metrics</h2><p>Guardrail and secondary metrics to watch for unexpected side effects.</p>
```

**Row 7 -- Segment Breakdown:**
```
<h2>Segment Breakdown</h2><p>Experiment results sliced by platform, plan, and geography.</p>
```

**Row 9 -- Funnel Impact:**
```
<h2>Funnel Impact</h2><p>How the experiment affects the core conversion funnel.</p>
```

**Row 11 -- Retention Impact:**
```
<h2>Retention Impact</h2><p>Whether the variant changes user return behavior over the first 4 weeks.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| Primary Lift | `{primary_metric_event}` | relative lift | Experiment group | % change vs control |
| Significance | `{primary_metric_event}` | p-value | Experiment group | Statistical confidence |
| Sample Size | `{primary_metric_event}` | `total_users` | Experiment group | Total enrolled users |
| Control vs variant | `{primary_metric_event}` | `total` or `dau` | Experiment group | Line chart over time |
| Secondary A | `{secondary_metric_event}` | `total` | Experiment group | Bar chart |
| Secondary B | `{login_event}` sessions | `avg_count_per_user` | Experiment group | Bar chart |
| By segment table | `{primary_metric_event}` | lift + significance | Experiment group x segment | Table with per-segment results |
| Funnel by group | `{signup_event}` > `{primary_metric_event}` | -- | Experiment group | Funnel segmented by group |
| Control retention | Born: `{signup_event}` (control), Return: `{login_event}` | -- | -- | 4-week curve |
| Variant retention | Born: `{signup_event}` (variant), Return: `{login_event}` | -- | -- | 4-week curve |

---

## Template 9: Operational Health Dashboard

**Description:** Monitor product reliability and performance with error rates, success metrics, user impact analysis, and recovery tracking.

**Use case:** Incident response, reliability monitoring, SLO tracking, post-incident reviews.

**Audience:** Engineering, SRE, product ops, on-call teams.

**Placeholder events:** `{error_event}`, `{login_event}`, `{core_action_event}`, `{page_view_event}`

### Layout

| Row | Content | Width | Height | Chart Type |
|---|---|---|---|---|
| 1 | Intro text card | w=12 | h=0 | text |
| 2 | KPI: Error Rate | w=3 | h=336 | insights-metric |
| 2 | KPI: P95 Latency | w=3 | h=336 | insights-metric |
| 2 | KPI: Success Rate | w=3 | h=336 | insights-metric |
| 2 | KPI: Active Users | w=3 | h=336 | insights-metric |
| 3 | Section header: Reliability Trends | w=12 | h=0 | text |
| 4 | Error rate trend | w=6 | h=418 | line |
| 4 | Success rate trend | w=6 | h=418 | line |
| 5 | Section header: Error Breakdown | w=12 | h=0 | text |
| 6 | Errors by type | w=12 | h=500 | bar |
| 7 | Section header: Error Dimensions | w=12 | h=0 | text |
| 8 | Errors by platform | w=6 | h=418 | bar |
| 8 | Errors by app version | w=6 | h=418 | bar |
| 9 | Section header: User Impact | w=12 | h=0 | text |
| 10 | Users affected by errors (table) | w=12 | h=588 | table |
| 11 | Section header: Recovery Patterns | w=12 | h=0 | text |
| 12 | Post-error user return rate | w=12 | h=500 | line |

### Text Card Content

**Row 1 -- Intro:**
```
<h2>Operational Health</h2><p>Product reliability, error rates, and user impact monitoring. Updated in near real-time.</p>
```

**Row 3 -- Reliability Trends:**
```
<h2>Reliability Trends</h2><p>Error rate and success rate over the last 30 days.</p>
```

**Row 5 -- Error Breakdown:**
```
<h2>Error Breakdown</h2><p>Errors categorized by type to identify systemic issues.</p>
```

**Row 7 -- Error Dimensions:**
```
<h2>Error Dimensions</h2><p>Error distribution across platforms and app versions.</p>
```

**Row 9 -- User Impact:**
```
<h2>User Impact</h2><p>How many users are affected by errors and how severely.</p>
```

**Row 11 -- Recovery Patterns:**
```
<h2>Recovery Patterns</h2><p>Whether users return to the product after encountering errors.</p>
```

### Report Specifications

| Report | Event | Math | Breakdown | Notes |
|---|---|---|---|---|
| Error Rate | `{error_event}` / `{core_action_event}` | ratio | -- | Compare to previous period |
| P95 Latency | `{page_view_event}` | `p95` of duration property | -- | Compare to previous period |
| Success Rate | `{core_action_event}` (success) / `{core_action_event}` (all) | ratio | -- | 1 - error rate |
| Active Users | `{login_event}` | `dau` | -- | Compare to previous period |
| Error rate trend | `{error_event}` | `total` | -- | Line chart, 30 days |
| Success rate trend | `{core_action_event}` | `total` | Success/failure status | Line chart, 30 days |
| By type | `{error_event}` | `total` | Error type property | Bar chart, top 10 |
| By platform | `{error_event}` | `total` | Platform | Bar chart |
| By version | `{error_event}` | `total` | App version | Bar chart, top 10 |
| Impact table | `{error_event}` | `total`, `dau` | Error type | Table: count, users, rate |
| Recovery rate | Born: `{error_event}`, Return: `{login_event}` | -- | -- | 7-day retention post-error |

---

## Template Selection Guide

Use this table to quickly match the user's request to the right template.

| User Says | Template | Why |
|---|---|---|
| "executive dashboard", "KPI overview", "key metrics" | 1: KPI Dashboard | High-level health metrics |
| "feature launch", "new feature tracking", "adoption" | 2: Feature Launch | Post-launch monitoring |
| "growth metrics", "pirate metrics", "AARRR", "full funnel" | 3: AARRR | End-to-end growth tracking |
| "funnel analysis", "conversion optimization", "drop-off" | 4: Conversion Funnel | Deep funnel investigation |
| "retention analysis", "churn", "cohort analysis" | 5: Retention | Retention deep dive |
| "engagement", "usage patterns", "power users" | 6: User Engagement | Engagement depth analysis |
| "marketing", "channels", "campaigns", "acquisition" | 7: Marketing Performance | Channel effectiveness |
| "A/B test", "experiment results", "variant comparison" | 8: Experiment Results | Experiment presentation |
| "errors", "reliability", "ops health", "SLO", "incidents" | 9: Operational Health | Reliability monitoring |
| Unclear or general request | 1: KPI Dashboard | Safe default |
