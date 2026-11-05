---
name: interpreting-culture-index
description: Interprets Culture Index (CI) surveys, behavioral profiles, and personality assessment data. Supports individual profile interpretation, team composition analysis (gas/brake/glue), burnout detection, profile comparison, hiring profiles, manager coaching, interview transcript analysis for trait prediction, candidate debrief, onboarding planning, and conflict mediation. Accepts extracted JSON or PDF input via OpenCV extraction script.
allowed-tools: Bash Read Grep Glob Write
---

<essential_principles>

**Culture Index measures behavioral traits, not intelligence or skills. There is no "good" or "bad" profile.**

<principle name="never-compare-absolutes">
**Never compare absolute trait values between people.**

The 0-10 scale is just a ruler. What matters is **distance from the red arrow** (population mean at 50th percentile). The arrow position varies between surveys based on EU.

**Why the arrow moves:** Higher EU scores cause the arrow to plot further right; lower EU causes it to plot further left. This does not affect validity—we always measure distance from wherever the arrow lands.

**Wrong**: "Dan has higher autonomy than Jim because his A is 8 vs 5"
**Right**: "Dan is +3 centiles from his arrow; Jim is +1 from his arrow"

Always ask: Where is the arrow, and how far is the dot from it?
</principle>

<principle name="survey-vs-job">
**Survey = who you ARE. Job = who you're TRYING TO BE.**

> **"You can't send a duck to Eagle school."** Traits are hardwired—you can only modify behaviors temporarily, at the cost of energy.

- **Top graph (Survey Traits)**: Hardwired by age 12-16. Does not change. Writing with your dominant hand.
- **Bottom graph (Job Behaviors)**: Adaptive behavior at work. Can change. Writing with your non-dominant hand.

Large differences between graphs indicate behavior modification, which drains energy and causes burnout if sustained 3-6+ months.
</principle>

<principle name="distance-interpretation">
**Distance from arrow determines trait strength.**

| Distance | Label | Percentile | Interpretation |
|----------|-------|------------|----------------|
| On arrow | Normative | 50th | Flexible, situational |
| ±1 centile | Tendency | ~67th | Easier to modify |
| ±2 centiles | Pronounced | ~84th | Noticeable difference |
| ±4+ centiles | Extreme | ~98th | Hardwired, compulsive, predictable |

**Key insight:** Every 2 centiles of distance = 1 standard deviation.

Extreme traits drive extreme results but are harder to modify and less relatable to average people.
</principle>

<principle name="l-and-i-exception">
**L (Logic) and I (Ingenuity) use absolute values.**

Unlike A, B, C, D, you CAN compare L and I scores directly between people:
- Logic 8 means "High Logic" regardless of arrow position
- Ingenuity 2 means "Low Ingenuity" for anyone

Only these two traits break the "no absolute comparison" rule.
</principle>

</essential_principles>

## When to Use

- Interpreting Culture Index survey results (individual or team)
- Analyzing CI profiles from PDF or JSON data
- Assessing team composition using Gas/Brake/Glue framework
- Detecting burnout risk by comparing Survey vs Job graphs
- Defining hiring profiles based on CI trait patterns
- Coaching managers on how to work with specific CI profiles
- Predicting CI traits from interview transcripts
- Mediating team conflict using CI profile data

## When NOT to Use

- For non-CI behavioral assessments (DISC, Myers-Briggs, StrengthsFinder, Predictive Index, Enneagram)
- For clinical psychological assessments or diagnoses
- As the sole basis for hiring/firing decisions — CI is one data point among many

<input_formats>

**JSON (Use if available)**

If JSON data is already extracted, use it directly:
```python
import json
with open("person_name.json") as f:
    profile = json.load(f)
```

JSON format:
```json
{
  "name": "Person Name",
  "archetype": "Architect",
  "survey": {
    "eu": 21,
    "arrow": 2.3,
    "a": [5, 2.7],
    "b": [0, -2.3],
    "c": [1, -1.3],
    "d": [3, 0.7],
    "logic": [5, null],
    "ingenuity": [2, null]
  },
  "job": { "..." : "same structure as survey" },
  "analysis": {
    "energy_utilization": 148,
    "status": "stress"
  }
}
```

Note: Trait values are `[absolute, relative_to_arrow]` tuples. Use the relative value for interpretation.

Check same directory as PDF for matching `.json` file, or ask user if they have extracted JSON.

**PDF Input (MUST EXTRACT FIRST)**

⚠️ **NEVER use visual estimation for trait values.** Visual estimation has 20-30% error rate.

When given a PDF:
1. Check if JSON already exists (same directory as PDF, or ask user)
2. If not, run extraction with verification:
   ```bash
   uv run {baseDir}/scripts/extract_pdf.py --verify /path/to/file.pdf [output.json]
   ```
3. Visually confirm the verification summary matches the PDF
4. Use the extracted JSON for interpretation

**If uv is not installed:** Stop and instruct user to install it (`brew install uv` or `pip install uv`). Do NOT fall back to vision.

**PDF Vision (Reference Only)**

Vision may be used ONLY to verify extracted values look reasonable, NOT to extract trait scores.

</input_formats>

<intake>

**Step 0: Do you have JSON or PDF?**

1. **If JSON provided or found:** Use it directly (skip extraction)
   - Check same directory as PDF for `.json` file with matching name
   - Check if user provided JSON path
2. **If only PDF:** Run extraction script with `--verify` flag
   ```bash
   uv run {baseDir}/scripts/extract_pdf.py --verify /path/to/file.pdf [output.json]
   ```
3. **If extraction fails:** Report error, do NOT fall back to vision

**Step 1: What data do you have?**

- **CI Survey JSON** → Proceed to Step 2
- **CI Survey PDF** → Extract first (Step 0), then proceed to Step 2
- **Interview transcript only** → Go to option 8 (predict traits from interview)
- **No data yet** → "Please provide Culture Index profile (PDF or JSON) or interview transcript"

**Step 2: What would you like to do?**

**Profile Analysis:**
1. **Interpret an individual profile** - Understand one person's traits, strengths, and challenges
2. **Analyze team composition** - Assess gas/brake/glue balance, identify gaps
3. **Detect burnout signals** - Compare Survey vs Job, flag stress/frustration
4. **Compare multiple profiles** - Understand compatibility, collaboration dynamics
5. **Get motivator recommendations** - Learn how to engage and retain someone

**Hiring & Candidates:**
6. **Define hiring profile** - Determine ideal CI traits for a role
7. **Coach manager on direct report** - Adjust management style based on both profiles
8. **Predict traits from interview** - Analyze interview transcript to estimate CI traits
9. **Interview debrief** - Assess candidate fit based on predicted traits

**Team Development:**
10. **Plan onboarding** - Design first 90 days based on new hire and team profiles
11. **Mediate conflict** - Understand friction between two people using their profiles

**Provide the profile data (JSON or PDF) and select an option, or describe what you need.**

</intake>

<routing>

| Response | Workflow |
|----------|----------|
| "extract", "parse pdf", "convert pdf", "get json from pdf" | `workflows/extract-from-pdf.md` |
| 1, "individual", "interpret", "understand", "analyze one", "single profile" | `workflows/interpret-individual.md` |
| 2, "team", "composition", "gaps", "balance", "gas brake glue" | `workflows/analyze-team.md` |
| 3, "burnout", "stress", "frustration", "survey vs job", "energy", "flight risk" | `workflows/detect-burnout.md` |
| 4, "compare", "compatibility", "collaboration", "multiple", "two profiles" | `workflows/compare-profiles.md` |
| 5, "motivate", "engage", "retain", "communicate" | Read `references/motivators.md` directly |
| 6, "hire", "hiring profile", "role profile", "recruit", "what profile for" | `workflows/define-hiring-profile.md` |
| 7, "manage", "coach", "1:1", "direct report", "manager" | `workflows/coach-manager.md` |
| 8, "transcript", "interview", "predict traits", "guess", "estimate", "recording" | `workflows/predict-from-interview.md` |
| 9, "debrief", "should we hire", "candidate fit", "proceed", "offer" | `workflows/interview-debrief.md` |
| 10, "onboard", "new hire", "integrate", "starting", "first 90 days" | `workflows/plan-onboarding.md` |
| 11, "conflict", "friction", "mediate", "not working together", "clash" | `workflows/mediate-conflict.md` |
| "conversation starters", "how to talk to", "engage with" | Read `references/conversation-starters.md` directly |

**After reading the workflow, follow it exactly.**

</routing>

<verification_loop>

After every interpretation, verify:

1. **Did you use relative positions?** Never stated "A is 8" without context
2. **Did you reference the arrow?** All trait interpretations relative to arrow
3. **Did you compare Survey vs Job?** Identified any behavior modification
4. **Did you avoid value judgments?** No traits called "good" or "bad"
5. **Did you check EU?** Energy utilization calculated if both graphs present

Report to user:
- "Interpretation complete"
- Key findings (2-3 bullet points)
- Recommended actions

</verification_loop>

<reference_index>

**Domain Knowledge** (in `references/`):

**Primary Traits:**
- `primary-traits.md` - A (Autonomy), B (Social), C (Pace), D (Conformity)

**Secondary Traits:**
- `secondary-traits.md` - EU (Energy Units), L (Logic), I (Ingenuity)

**Patterns:**
- `patterns-archetypes.md` - Behavioral patterns, trait combinations, archetypes

**Archetype Deep Profiles** (`archetype-*.md`):
- `archetype-administrator.md` - The Administrator (High A, High B, Low C, Mid D)
- `archetype-coordinator.md` - The Coordinator (Low A, High B, Mid C, Low D)
- `archetype-craftsman.md` - The Craftsman (Low A, Low B, High C, High D)
- `archetype-daredevil.md` - The Daredevil (High A, Low B, Low C, Low D)
- `archetype-debater.md` - The Debater (Mid A, Mid-High B, Low C, High D)
- `archetype-facilitator.md` - The Facilitator (Low A, Mid B, Mid C, Low D)
- `archetype-influencer.md` - The Influencer (Low A, High B, Low C, Low D)
- `archetype-operator.md` - The Operator (Low A, Low B, High C, Mid-High D)
- `archetype-persuader.md` - The Persuader (High A, High B, Low C, Low D)
- `archetype-philosopher.md` - The Philosopher (Low A, Low B, High C, Low D)
- `archetype-rainmaker.md` - The Rainmaker (High A, High B, Low C, Low D)
- `archetype-scholar.md` - The Scholar (High A, Low B, Low C, High D)
- `archetype-socializer.md` - The Socializer (Low A, High B, Low C, Low D)
- `archetype-specialist.md` - The Specialist (Low A, Low B, High C, Mid D)
- `archetype-technical-expert.md` - The Technical Expert (Low A, Low B, High C, Low D)
- `archetype-traditionalist.md` - The Traditionalist (Low A, Low B, High C, High D)
- `archetype-trailblazer.md` - The Trailblazer (High A, Mid B, Mid C, Low D)

**Application:**
- `motivators.md` - How to motivate each trait type
- `team-composition.md` - Gas, brake, glue framework
- `anti-patterns.md` - Common interpretation mistakes
- `conversation-starters.md` - How to engage each pattern and trait type
- `interview-trait-signals.md` - Signals for predicting traits from interviews

</reference_index>

<workflows_index>

**Workflows** (in `workflows/`):

| File | Purpose |
|------|---------|
| `extract-from-pdf.md` | Extract profile data from Culture Index PDF to JSON format |
| `interpret-individual.md` | Analyze single profile, identify archetype, summarize strengths/challenges |
| `analyze-team.md` | Assess team balance (gas/brake/glue), identify gaps, recommend hires |
| `detect-burnout.md` | Compare Survey vs Job, calculate EU utilization, flag risk signals |
| `compare-profiles.md` | Compare multiple profiles, assess compatibility, collaboration dynamics |
| `define-hiring-profile.md` | Define ideal CI traits for a role, identify acceptable patterns and red flags |
| `coach-manager.md` | Help managers adjust their style for specific direct reports |
| `predict-from-interview.md` | Analyze interview transcripts to predict CI traits before survey |
| `interview-debrief.md` | Assess candidate fit using predicted traits from transcript analysis |
| `plan-onboarding.md` | Design first 90 days based on new hire profile and team composition |
| `mediate-conflict.md` | Understand and address friction between team members using their profiles |

</workflows_index>

<quick_reference>

**Trait Colors:**
| Trait | Color | Measures |
|-------|-------|----------|
| A | Maroon | Autonomy, initiative, self-confidence |
| B | Yellow | Social ability, need for interaction |
| C | Blue | Pace/Patience, urgency level |
| D | Green | Conformity, attention to detail |
| L | Purple | Logic, emotional processing |
| I | Cyan | Ingenuity, inventiveness |

**Energy Utilization Formula:**
```
Utilization = (Job EU / Survey EU) × 100

70-130% = Healthy
>130% = STRESS (burnout risk)
<70% = FRUSTRATION (flight risk)
```

**Gas/Brake/Glue:**
| Role | Trait | Function |
|------|-------|----------|
| Gas | High A | Growth, risk-taking, driving results |
| Brake | High D | Quality control, risk aversion, finishing |
| Glue | High B | Relationships, morale, culture |

**Score Precision:**
| Value | Precision | Example |
|-------|-----------|---------|
| Traits (A,B,C,D,L,I) | Integer 0-10 | 0, 1, 2, ... 10 |
| Arrow position | Tenths | 0.4, 2.2, 3.8 |
| Energy Units (EU) | Integer | 11, 31, 45 |

</quick_reference>

<success_criteria>

A well-interpreted Culture Index profile:
- Uses relative positions (distance from arrow), never absolute values alone
- Identifies the archetype/pattern correctly
- Highlights 2-3 key strengths based on leading traits
- Notes 2-3 challenges or development areas
- Compares Survey vs Job if both are available
- Provides actionable recommendations
- Avoids value judgments ("good"/"bad")
- Acknowledges Culture Index is one data point, not a complete picture

</success_criteria>
