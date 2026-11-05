<required_reading>

**Read these reference files before interpreting:**
1. `references/primary-traits.md` - A, B, C, D trait details
2. `references/secondary-traits.md` - EU, L, I traits
3. `references/patterns-archetypes.md` - Pattern identification

</required_reading>

<process>

**Step 1: Load the Profile**

For JSON:
```python
import json
with open("path/to/profile.json") as f:
    profile = json.load(f)
```

For PDF: **Extract first** using the extraction script:
```bash
uv run {baseDir}/scripts/extract_pdf.py --verify /path/to/profile.pdf
```

⚠️ **NEVER use visual estimation for trait values.** Visual estimation has 20-30% error rate.

**Step 1b: Verify Extraction (if from PDF)**

After extraction, review the verification summary and briefly spot-check against the PDF image:
- [ ] EU values match what's displayed on each chart
- [ ] Arrow position looks correct
- [ ] Most extreme trait (shown in summary) makes visual sense

If any value seems wrong, re-run extraction or report the discrepancy.

**Step 2: Identify Arrow Position**

The red vertical arrow is the population mean (50th percentile). Record its position on the 0-10 scale for both Survey and Job charts.

**Step 3: Calculate Trait Distances**

For each trait (A, B, C, D), calculate distance from arrow:

| Trait | Absolute Value | Arrow | Distance | Interpretation |
|-------|---------------|-------|----------|----------------|
| A | ? | ? | ? | (will fill) |
| B | ? | ? | ? | |
| C | ? | ? | ? | |
| D | ? | ? | ? | |

**Distance interpretation:**
- 0 to ±0.5: Normative (flexible)
- ±1 to ±1.5: Tendency (moderate)
- ±2 to ±3: Pronounced (noticeable)
- ±4+: Extreme (compulsive)

**Step 4: Identify Leading Dots**

Find the dots farthest from the arrow. These drive behavior most strongly.

Rank by distance (most extreme first):
1. [Trait] at ±X centiles
2. [Trait] at ±X centiles
3. [Trait] at ±X centiles

**Step 5: Identify Pattern/Archetype**

Cross-reference with `references/patterns-archetypes.md`.

Common patterns:
- **Architect/Visionary**: High A, Low C, Low D
- **Rainmaker/Persuader**: High A, High B, Low C
- **Scholar/Specialist**: Low B, High C, High D
- **Technical Expert**: Low A, Low B, Low C, High D
- **Craftsman**: Low A, Low B, High C, High D

**Step 6: Note L and I (Absolute Values)**

These use absolute interpretation, not distance from arrow:

| Trait | Score | Interpretation |
|-------|-------|----------------|
| Logic | 0-2: Low (emotional) | 3-7: Normative | 8-10: High (rational) |
| Ingenuity | 0-2: Low (practical) | 3-6: Occasional | 7-10: High (inventive) |

**Step 7: Summarize Strengths**

Based on leading dots, identify 2-3 key strengths:

For High A: Initiative, self-confidence, strategic thinking
For High B: Relationship building, influence, verbal communication
For High C: Patience, focus, consistency, methodical approach
For High D: Precision, reliability, quality control, accountability
For Low A: Team orientation, service mindset, execution
For Low B: Focus, analytical depth, independence
For Low C: Urgency, multitasking, adaptability
For Low D: Flexibility, big-picture thinking, risk tolerance

**Step 8: Identify Challenges**

Based on leading dots, note 2-3 potential challenges:

For High A: Difficulty with people, impatience with others, "me first" tendency
For High B: May prioritize relationships over results, needs social interaction
For High C: May resist change, slow to pivot, needs advance notice
For High D: May be inflexible, perfectionist, struggle to delegate
For Low A: May lack initiative, need clear direction, conflict avoidant
For Low B: May seem cold or disengaged, prefers solitude
For Low C: May create unnecessary urgency, interrupt others, prone to errors
For Low D: May miss details, inconsistent follow-through, forgetful

**Step 9: Check Survey vs Job**

If both graphs available, compare:
- Which dots moved significantly?
- Did arrow shift (stress/frustration signal)?
- Calculate EU utilization: (Job EU / Survey EU) × 100

**Step 10: Compile Summary**

Structure your interpretation:

```
## [Name] - [Archetype]

### Key Traits
- [Leading trait 1]: [interpretation]
- [Leading trait 2]: [interpretation]
- [Leading trait 3]: [interpretation]

### Strengths
1. [Strength 1]
2. [Strength 2]
3. [Strength 3]

### Development Areas
1. [Challenge 1]
2. [Challenge 2]

### Energy Status
- Survey EU: [X]
- Job EU: [X]
- Utilization: [X]% ([healthy/stress/frustration])

### Recommendations
- [Actionable recommendation 1]
- [Actionable recommendation 2]
```

</process>

<anti_patterns>

Avoid these interpretation mistakes:

- **Stating absolute values without context**: Never say "A is 8" without relating to arrow
- **Comparing between people using absolutes**: "Person A has higher B than Person B"
- **Value judgments**: Calling traits "good" or "bad"
- **Over-indexing on single traits**: The pattern matters more than individual dots
- **Ignoring Survey vs Job comparison**: Missing burnout signals
- **Treating as definitive**: Culture Index is one data point, not complete truth

</anti_patterns>

<success_criteria>

Individual interpretation is complete when:
- [ ] Data extracted using script (NOT visual estimation) if from PDF
- [ ] Verification summary spot-checked against PDF (if from PDF)
- [ ] Arrow position identified for both charts (if available)
- [ ] All trait distances calculated relative to arrow
- [ ] Leading dots identified and ranked
- [ ] Pattern/archetype named
- [ ] L and I interpreted using absolute values
- [ ] 2-3 strengths documented
- [ ] 2-3 challenges documented
- [ ] Survey vs Job compared (if available)
- [ ] EU utilization calculated (if both charts available)
- [ ] Actionable recommendations provided
- [ ] No absolute value comparisons used

</success_criteria>
