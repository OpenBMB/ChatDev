<required_reading>

**Read these reference files before analyzing:**
1. `references/interview-trait-signals.md` - Behavioral signals for each trait
2. `references/primary-traits.md` - A, B, C, D trait details
3. `references/secondary-traits.md` - L, I trait details
4. `references/patterns-archetypes.md` - Pattern identification

</required_reading>

<purpose>

Predict Culture Index traits from interview transcripts. This workflow is used when:
- Candidates have been interviewed but haven't taken the CI survey yet
- You want preliminary trait estimates before extending an offer
- You want to compare predicted vs actual CI (after offer is signed)

**Important:** This produces predictions, not diagnoses. The actual CI survey will be administered after an offer is signed and before the start date.

</purpose>

<process>

**Step 1: Load the Transcript**

Request the interview transcript. Ideal format includes:
- Interviewer questions clearly marked
- Candidate responses clearly marked
- Timestamps or durations (helpful but not required)
- Multiple interviews if available (more data = higher confidence)

**Step 2: Initial Read-Through**

First pass - get overall impression:
- How does the candidate communicate?
- What's their energy level?
- What topics engage them most?
- What's their default communication style?

Note your initial gut sense before detailed analysis.

**Step 3: Analyze A (Autonomy) Signals**

Search transcript for:

| Look For | High A | Low A |
|----------|--------|-------|
| Pronouns | "I decided", "I built" | "We decided", "Our team" |
| Credit | Takes personal credit | Deflects to team |
| Questions | Reframes, pushes back | Asks for clarification |
| Initiative | Acted without being asked | Waited for direction |
| Tone | Assertive, confident | Tentative, collaborative |

**Record:**
- Position: High / Low / Normative
- Confidence: High / Medium / Low
- Key quotes (2-3 examples)

**Step 4: Analyze B (Social) Signals**

Search transcript for:

| Look For | High B | Low B |
|----------|--------|-------|
| Rapport | Builds connection, asks about interviewer | Gets straight to business |
| Stories | People-centric narratives | Task-centric descriptions |
| Responses | Verbose, talks through thinking | Brief, direct answers |
| Energy | Animated, expressive | Reserved, measured |
| Culture questions | Asks about team, social activities | Asks about work, tools |

**Record:**
- Position: High / Low / Normative
- Confidence: High / Medium / Low
- Key quotes (2-3 examples)

**Step 5: Analyze C (Pace) Signals**

Search transcript for:

| Look For | High C | Low C |
|----------|--------|-------|
| Response speed | Pauses, thinks before answering | Rapid responses |
| Structure | Methodical, sequential | Topic-jumps, tangents |
| Ambiguity | Asks for clarification | Comfortable with unknowns |
| Change | Prefers stability | Thrives with pivots |
| Detail | One topic at a time | Multi-threads |

**Record:**
- Position: High / Low / Normative
- Confidence: High / Medium / Low
- Key quotes (2-3 examples)

**Step 6: Analyze D (Conformity) Signals**

Search transcript for:

| Look For | High D | Low D |
|----------|--------|-------|
| Precision | Specific numbers, dates | Approximations, ranges |
| Process | References rules, best practices | Describes creative approaches |
| Answers | Structured, follows question format | Free-flowing, interpretive |
| Quality | Mentions checking work, standards | Mentions outcomes, results |
| Flexibility | Follows structure | Challenges premises |

**Record:**
- Position: High / Low / Normative
- Confidence: High / Medium / Low
- Key quotes (2-3 examples)

**Step 7: Analyze L (Logic) - Absolute Scale**

Search transcript for:

| Look For | High L (8-10) | Low L (0-2) |
|----------|---------------|-------------|
| Framing | Data-driven, analytical | Values-driven, emotional |
| Language | "The numbers showed..." | "It felt right..." |
| Difficult topics | Emotion-neutral | Empathetic, emotional |
| Decision-making | Evidence-based | Intuition-based |

**Record:**
- Score estimate: 0-10
- Confidence: High / Medium / Low
- Key quotes (1-2 examples)

**Step 8: Analyze I (Ingenuity) - Absolute Scale**

Search transcript for:

| Look For | High I (7-10) | Low I (0-2) |
|----------|---------------|-------------|
| Problem-solving | Novel approaches | Proven methods |
| Assumptions | Questions, challenges | Accepts, follows |
| Examples | Original, creative | Standard, textbook |
| Routine | Mentions boredom | Describes comfort |

**Record:**
- Score estimate: 0-10
- Confidence: High / Medium / Low
- Key quotes (1-2 examples)

**Step 9: Identify Pattern**

Based on trait positions, identify likely pattern:

Cross-reference with `references/patterns-archetypes.md`:

| If you see... | Likely pattern |
|---------------|----------------|
| High A, Low B, Low C, Low D | Architect/Visionary |
| High A, High B, Low C | Rainmaker/Persuader |
| Low A, Low B, High C, High D | Scholar/Specialist |
| Low A, High B, High C | Accommodator |
| Low A, Low B, Low C, High D | Technical Expert |

**Only identify pattern if confidence is sufficient** - if traits are unclear, note "insufficient data for pattern identification."

**Step 10: Flag Uncertainty Areas**

Document where evidence is weak:
- Traits with only 1-2 data points
- Traits that showed inconsistent signals
- Topics that weren't covered in interview
- Signs of "interview mode" performance

**Step 11: Generate Predicted Profile**

Output using this structure:

```markdown
## Predicted Culture Index Profile: [Candidate Name]

**Analysis Date:** [Date]
**Transcript Source:** [Interview type, duration, interviewers]
**Overall Confidence:** [High/Medium/Low]

### Trait Predictions

| Trait | Predicted | Confidence | Evidence |
|-------|-----------|------------|----------|
| A (Autonomy) | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| B (Social) | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| C (Pace) | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| D (Conformity) | [High/Low/Norm] | [H/M/L] | "[Quote]" |
| L (Logic) | [0-10] | [H/M/L] | "[Quote]" |
| I (Ingenuity) | [0-10] | [H/M/L] | "[Quote]" |

### Predicted Pattern
**[Pattern Name]** (if identifiable)

[1-2 sentence description of what this pattern means]

### Strongest Signals
1. [Most clear trait signal with quote]
2. [Second clearest signal with quote]

### Uncertainty Areas
- [Trait/area where more data needed]
- [Trait/area where signals were mixed]

### Interview Context Notes
- [Any factors that may have affected behavior]
- [Signs of interview performance mode]

### Caveats
- This is a prediction based on interview behavior, not a CI survey result
- Interview stress may affect natural behavior patterns
- Actual CI survey will be administered after offer acceptance
- Use for preliminary assessment only - do not treat as definitive
```

</process>

<verification>

Before finalizing prediction:

1. **Did I cite specific quotes?** Every trait prediction needs evidence
2. **Did I note confidence levels?** Every trait needs H/M/L confidence
3. **Did I flag uncertainties?** Where is evidence weak?
4. **Did I include caveats?** Predictions are not diagnoses
5. **Did I avoid over-confidence?** Especially for low-data traits

</verification>

<anti_patterns>

Avoid these prediction mistakes:

- **Over-interpreting single quotes**: One example isn't a pattern
- **Ignoring interview context**: Stress affects behavior
- **Treating predictions as definitive**: This is hypothesis, not diagnosis
- **Skipping low-confidence traits**: Better to say "uncertain" than guess
- **Assuming consistency**: Interview behavior may differ from daily behavior
- **Forgetting to cite evidence**: Every claim needs a quote

</anti_patterns>

<success_criteria>

Transcript analysis is complete when:
- [ ] All 6 traits analyzed with position/score estimates
- [ ] Each trait has confidence level (H/M/L)
- [ ] Each trait has supporting quotes from transcript
- [ ] Pattern identified (if sufficient confidence)
- [ ] Uncertainty areas documented
- [ ] Caveats clearly stated
- [ ] Output follows standard format

</success_criteria>
