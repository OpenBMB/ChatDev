<required_reading>

**Read these reference files before debrief:**
1. `references/patterns-archetypes.md` - Pattern identification and role fit
2. `references/team-composition.md` - Gas/Brake/Glue framework
3. `workflows/predict-from-interview.md` - How predictions were generated
4. `workflows/define-hiring-profile.md` - If hiring profile exists

</required_reading>

<purpose>

Evaluate a candidate's predicted Culture Index profile against role requirements and team composition. This workflow helps make informed hiring decisions using transcript-predicted traits, with appropriate caveats about prediction confidence.

**Important:** This uses PREDICTED traits from interview analysis, not actual CI survey results. The actual survey will be administered after offer acceptance. Use this for preliminary assessment only.

</purpose>

<process>

**Step 1: Load Predicted Profile**

Gather the prediction from transcript analysis:

```
Candidate: [Name]
Analysis Date: [Date]
Interview Source: [Interview type, duration]

Predicted Traits:
| Trait | Predicted | Confidence | Key Evidence |
|-------|-----------|------------|--------------|
| A | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| B | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| C | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| D | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| L | [0-10] | [H/M/L] | "[Quote]" |
| I | [0-10] | [H/M/L] | "[Quote]" |

Predicted Pattern: [Pattern name]
Overall Confidence: [High/Medium/Low]
```

**Step 2: Load Role Requirements**

If a hiring profile exists, load it. Otherwise, answer the role-fit questions:

| Question | Answer | Required Trait |
|----------|--------|----------------|
| Macro or micro? | [answer] | A: [High/Low/Norm] |
| People or problems? | [answer] | B: [High/Low/Norm] |
| Repetition level? | [answer] | C: [High/Low/Norm] |
| Process adherence? | [answer] | D: [High/Low/Norm] |

**Target Pattern:** [Pattern name]
**Red Flags for Role:** [traits that would struggle]

**Step 3: Compare Predicted vs Required**

| Trait | Predicted | Required | Match | Notes |
|-------|-----------|----------|-------|-------|
| A | [pred] | [req] | [Y/N/~] | [concern if any] |
| B | [pred] | [req] | [Y/N/~] | [concern if any] |
| C | [pred] | [req] | [Y/N/~] | [concern if any] |
| D | [pred] | [req] | [Y/N/~] | [concern if any] |
| L | [pred] | [req] | [Y/N/~] | [concern if any] |
| I | [pred] | [req] | [Y/N/~] | [concern if any] |

**Match key:**
- Y = Strong match (same direction, similar magnitude)
- ~ = Acceptable (within tolerance)
- N = Mismatch (opposite direction or extreme gap)

**Step 4: Check Against Red Flags**

Compare predicted traits to role red flags:

| Red Flag | Predicted | Hit? | Severity |
|----------|-----------|------|----------|
| [trait/pattern] | [prediction] | [Y/N] | [High/Med/Low] |

**Red flag hits:** [count]

**Step 5: Assess Team Fit**

If team profiles are available:

**Current Team Composition:**
- Gas (High A): [count] people
- Brake (High D): [count] people
- Glue (High B): [count] people

**Would this candidate add:**
- [ ] Needed Gas (High A)?
- [ ] Needed Brake (High D)?
- [ ] Needed Glue (High B)?
- [ ] Diversity of perspective?

**Potential team friction:**
- [Candidate trait] vs [Team member trait]: [friction risk]

**Step 6: Assess Manager Fit**

If hiring manager's profile is known:

| Trait | Manager | Candidate (Predicted) | Gap |
|-------|---------|----------------------|-----|
| A | [pos] | [pred] | [diff] |
| B | [pos] | [pred] | [diff] |
| C | [pos] | [pred] | [diff] |
| D | [pos] | [pred] | [diff] |

**Predicted working relationship:**
- [Alignment or friction point 1]
- [Alignment or friction point 2]

**Step 7: Weight Confidence Levels**

Calculate weighted assessment based on prediction confidence:

| Factor | Assessment | Confidence Weight | Weighted |
|--------|------------|-------------------|----------|
| Role fit | [Strong/Moderate/Weak] | [H/M/L → 3/2/1] | [score] |
| Team fit | [Strong/Moderate/Weak] | [H/M/L → 3/2/1] | [score] |
| Red flag hits | [None/Some/Multiple] | [H/M/L → 3/2/1] | [score] |
| Manager fit | [Strong/Moderate/Weak] | [H/M/L → 3/2/1] | [score] |

**Important confidence caveats:**
- Low confidence traits: May change significantly when actual CI is administered
- Medium confidence: Directionally correct but magnitude uncertain
- High confidence: Likely accurate, but interview stress may have affected

**Step 8: Generate Recommendation**

Based on weighted assessment:

| Overall Fit | Recommendation | Action |
|-------------|----------------|--------|
| Strong fit, high confidence | **Proceed** | Extend offer, plan for CI survey |
| Strong fit, low confidence | **Proceed with note** | Extend offer, flag traits to verify |
| Moderate fit | **Proceed with awareness** | Extend offer, prepare for onboarding adjustments |
| Weak fit, concerns | **Discuss** | Review concerns with hiring team |
| Red flag hits | **Pause** | Additional interviews or reconsider |

**Step 9: Compile Debrief Summary**

```markdown
## Interview Debrief: [Candidate Name]

**Date:** [Date]
**Role:** [Position]
**Prediction Source:** [Interview type, duration]
**Overall Prediction Confidence:** [High/Medium/Low]

### Predicted Profile Summary
| Trait | Predicted | Confidence |
|-------|-----------|------------|
| A | [pos] | [H/M/L] |
| B | [pos] | [H/M/L] |
| C | [pos] | [H/M/L] |
| D | [pos] | [H/M/L] |

**Predicted Pattern:** [Pattern]

### Fit Assessment

**Role Fit:** [Strong/Moderate/Weak]
- [Key alignment or concern]

**Team Fit:** [Strong/Moderate/Weak]
- [Key alignment or concern]

**Manager Fit:** [Strong/Moderate/Weak]
- [Key alignment or concern]

### Red Flags
- [Red flag 1, if any]
- [Red flag 2, if any]

### Recommendation
**[Proceed / Proceed with Note / Discuss / Pause]**

[1-2 sentence rationale]

### Areas to Verify with Actual CI
When the actual Culture Index survey is administered (after offer acceptance), verify:
1. [Trait with lower confidence]
2. [Trait that's critical for role]
3. [Any predicted trait that was borderline]

### If Hired: Onboarding Considerations
Based on predicted profile:
- [Onboarding consideration 1]
- [Onboarding consideration 2]

### Caveats
- This assessment uses predicted traits from interview analysis
- Interview behavior may differ from natural behavior
- Actual CI survey will be sent after offer acceptance
- Predictions should inform, not determine, hiring decisions
- Technical skills, experience, and cultural interview still matter
```

</process>

<anti_patterns>

Avoid these debrief mistakes:

- **Treating predictions as facts**: Low confidence predictions may be wrong
- **Over-weighting CI fit**: Skills, experience, and culture interview matter too
- **Automatic rejection on red flags**: Consider severity and role criticality
- **Ignoring interview performance**: CI predicts drives, not capabilities
- **Comparing to non-existent ideal**: No candidate is a perfect match
- **Forgetting the actual survey is coming**: Use predictions for preliminary assessment only

</anti_patterns>

<success_criteria>

Interview debrief is complete when:
- [ ] Predicted profile loaded with confidence levels
- [ ] Role requirements documented (from hiring profile or role-fit questions)
- [ ] Predicted vs required comparison completed
- [ ] Red flags checked
- [ ] Team fit assessed (if team data available)
- [ ] Manager fit assessed (if manager profile available)
- [ ] Confidence weighting applied
- [ ] Clear recommendation generated
- [ ] Areas to verify with actual CI identified
- [ ] Onboarding considerations noted
- [ ] Caveats about prediction limitations included

</success_criteria>
