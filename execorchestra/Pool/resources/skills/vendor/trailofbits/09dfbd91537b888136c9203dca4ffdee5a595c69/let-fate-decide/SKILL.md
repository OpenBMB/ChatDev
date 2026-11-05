---
name: let-fate-decide
description: "Draws the 12 Houses of the Zodiac Tarot spread to inject entropy into planning when prompts are vague, ambiguous, or casually delegated. Interprets the spread to guide next steps. Use when the user says 'let fate decide', 'YOLO', 'whatever', 'idk', or other nonchalant phrases, makes Yu-Gi-Oh references, or when you are about to arbitrarily pick between multiple reasonable approaches. Prefer over ask-questions-if-underspecified when the user's tone is casual or playful rather than precision-seeking."
allowed-tools: Bash Read Grep Glob
---

# Let Fate Decide

When the path forward is unclear, let the cards speak.

## Quick Start

1. Run the drawing script:
   ```bash
   uv run --no-config {baseDir}/scripts/draw_cards.py
   ```

2. The script outputs JSON for the default 12 Houses of the Zodiac spread:
   12 houses, each with 1 Major Arcana card and 2 Minor Arcana cards. Each
   house and card includes a `file` path relative to `{baseDir}/`

3. Read each house file and each card's meaning file to understand the draw.
   For faster reads, use `--content` to include house and card text directly
   in the JSON:
   ```bash
   uv run --no-config {baseDir}/scripts/draw_cards.py --content
   ```

4. Interpret the spread using the guide at [{baseDir}/references/INTERPRETATION_GUIDE.md]({baseDir}/references/INTERPRETATION_GUIDE.md)

5. When the task belongs to a specialized technical workflow, use
   [{baseDir}/references/TECHNICAL_CONTEXT_LENSES.md]({baseDir}/references/TECHNICAL_CONTEXT_LENSES.md)
   to translate the reading into an audit, verification, domain, failure-class,
   or stakeholder lens

6. Apply the interpretation to the task at hand

## When to Use

- **Vague prompts**: The user's request is ambiguous and multiple reasonable approaches exist
- **Explicit invocations**: "I'm feeling lucky", "let fate decide", "dealer's choice", "surprise me", "whatever you think", "YOLO"
- **Casual delegation**: "whatever", "up to you", "your call", "idk", "just do something", "wing it", "I trust you", "doesn't matter", "do what you want", "I don't care", "any approach works", "you pick"
- **Yu-Gi-Oh energy**: "Heart of the cards", "I believe in the heart of the cards", "you've activated my trap card", "it's time to duel"
- **Shrug-like brevity**: Very short prompts that fully delegate the decision without expressing a preference
- **Redraw requests**: "Try again" or "draw again" when no actual system changes occurred (this means draw new cards, not re-run the same approach)
- **Tie-breaking**: When you are about to arbitrarily pick between 2+ valid approaches, draw cards instead of silently choosing one

## When NOT to Use

- The user has given clear, specific instructions
- The task has a single obvious correct approach
- As the deciding authority for safety-critical work (security, data integrity,
  production deployments, release approval, incident response)
- The user explicitly asks you NOT to use Tarot
- The user's tone is precision-seeking rather than casual -- use `ask-questions-if-underspecified` instead to gather actual requirements

## Security and Correctness Use

This skill may be used inside a security, audit, or correctness pipeline as a
creative lens for discovery: choosing which angle to inspect next, breaking
analysis paralysis, generating hypotheses, or surfacing blind spots.

It is never sufficient by itself. In security and correctness contexts, the
reading must be followed by ordinary engineering evidence: source review,
tests, proofs, traces, reproduction steps, exploitability analysis, or other
domain-appropriate verification. Do not treat a favorable card as permission to
ship, suppress a finding, skip validation, or overrule a concrete risk.

## How It Works

### The Draw

The script uses `secrets` for cryptographic randomness:

1. Builds separate Major Arcana (22 cards) and Minor Arcana (56 cards) decks
2. Performs Fisher-Yates shuffles via `secrets.randbelow()` (no modulo bias)
3. Deals the default 12 Houses of the Zodiac spread
4. Each house receives 1 Major Arcana card followed by 2 Minor Arcana cards
5. Each of the 36 cards independently has a 50% chance of being reversed

The default spread records a conservative unordered-card entropy budget
exceeding 100 bits: roughly `log2(C(22,12))` bits from Major Arcana selection,
`log2(C(56,24))` bits from Minor Arcana selection (assuming
`secrets.randbelow()` is cryptographically secure), plus 36 reversal bits. The
exact values are computed and reported in the JSON output under `entropy_bits`.
The actual ordered assignment of cards to houses contains more entropy.

### The Spread

The default spread is **12 Houses of the Zodiac**:

| House | Represents | Question It Answers |
|-------|------------|---------------------|
| 1 | **Self** | How should this work begin? |
| 2 | **Resources** | What values, assets, or constraints matter? |
| 3 | **Communication** | What needs to be clarified or connected? |
| 4 | **Foundations** | What context or dependency anchors the task? |
| 5 | **Creativity** | Where should experimentation or delight shape the work? |
| 6 | **Practice** | What quality, maintenance, or execution concern matters? |
| 7 | **Partnership** | Who or what must this integrate with? |
| 8 | **Transformation** | What risk, shared state, or deep change is present? |
| 9 | **Exploration** | What principle or broader strategy guides the path? |
| 10 | **Calling** | What delivery or long-term outcome is being served? |
| 11 | **Community** | What system, network, or shared aspiration is involved? |
| 12 | **The Hidden** | What blind spot, ending, or unconscious factor matters? |

Within each house, the Major Arcana card sets the archetypal theme and the two
Minor Arcana cards provide practical detail.

For compatibility with older workflows, `draw_cards.py --legacy` returns the
previous 4-card hand, and `draw_cards.py --legacy <count>` returns a custom
hand of 1-78 cards. A positional count without `--legacy` is rejected, because
the new default spread has a fixed shape.

### Reference Files

Each house's meaning is in its own markdown file under `{baseDir}/houses/`.
House files describe how the house applies across technical contexts including
building new projects, vulnerability discovery, correctness verification, and
common audit, verification, domain, failure-class, and stakeholder workflows.

Each card's meaning is in its own markdown file under `{baseDir}/cards/`:

- `cards/major/` - 22 Major Arcana (archetypal forces)
- `cards/wands/` - 14 Wands (creativity, action, will)
- `cards/cups/` - 14 Cups (emotion, intuition, relationships)
- `cards/swords/` - 14 Swords (intellect, conflict, truth)
- `cards/pentacles/` - 14 Pentacles (material, practical, craft)

### Interpretation

After drawing, read each house file and each card file, then synthesize
meaning. See [{baseDir}/references/INTERPRETATION_GUIDE.md]({baseDir}/references/INTERPRETATION_GUIDE.md) for the full interpretation workflow.
For cross-domain translation, see
[{baseDir}/references/TECHNICAL_CONTEXT_LENSES.md]({baseDir}/references/TECHNICAL_CONTEXT_LENSES.md).

Key rules:
- Reversed cards invert or complicate the upright meaning
- Major Arcana cards carry more weight than Minor Arcana
- The spread tells a story across all 12 houses; don't interpret cards in isolation
- Map abstract meanings to concrete technical decisions
- In security, audit, and correctness work, use the reading to choose an
  investigation path, then require evidence before accepting or dismissing any
  risk
- **Never output interpretation as a text-only turn.** Include the
  interpretation alongside your next tool call (the action that
  implements the chosen option). Prefer `--content` so all 36 card
  meanings and all 12 house meanings are available from the draw output.

## Example Session (House-Level Fragment)

A real reading synthesizes all 12 houses; the fragment below shows only what
one house contributes so the format is clear. Do not stop after one house in
actual use.

```
User: "I dunno, just make it work somehow"

[Draw cards]
1st House (Self): The Magician (upright), Five of Swords (reversed),
                  Ten of Pentacles (upright)

House contribution: The starting stance is resourceful and tool-rich
(Magician), but the practical details warn against combative edge-case work
(Five of Swords reversed) while still favoring maintainable craft
(Ten of Pentacles). This is one input into the overall reading; combine with
the remaining 11 houses before deciding on an approach.
```

The named `draw` agent returns a more compact form for portent questions:
3 concise bullets covering the dominant theme, the main risk or blind spot,
and the recommended next action.

## Error Handling

If the drawing script fails:
- **Script crashes with traceback**: Report the error to the user and skip the reading. Do not invent cards or simulate a draw — the whole point is real entropy.
- **Card file not found**: Note the missing file, interpret the card from its name and suit alone, and continue with the reading.
- **Never fake entropy**: If the script cannot run, do not simulate a draw using your own "randomness." Tell the user the draw failed.

## Rationalizations to Reject

| Rationalization | Why Wrong |
|----------------|-----------|
| "The cards said to, so I must" | Cards inform direction, they don't override safety or correctness |
| "This reading justifies my pre-existing preference" | Be honest if the reading challenges your instinct |
| "The reversed card means do nothing" | Reversed means a different angle, not inaction |
| "Major Arcana overrides user requirements" | User requirements always take priority over card readings |
| "I'll keep drawing until I get what I want" | One draw per decision point; accept the reading |
| "The reading says the risk is fine" | Cards can suggest what to inspect; only evidence can dismiss a security or correctness concern |
