# Interpretation Guide

How to read the 12 Houses of the Zodiac Tarot spread and map it to technical
decisions.

## The Spread Positions

Each house contains 3 cards:

- The first card is always Major Arcana and sets the house's archetypal theme.
- The second and third cards are Minor Arcana and supply practical details.
- The house file under `houses/` explains how that house maps to technical
  contexts such as building, vulnerability discovery, and correctness work.
- `TECHNICAL_CONTEXT_LENSES.md` maps common technical workflows to reusable
  audit, evidence, domain, failure-class, and human/organizational lenses.

| House | Role | Maps To |
|-------|------|---------|
| 1 - Self | Identity, agency, first impulse | How to begin, the operating stance |
| 2 - Resources | Values, assets, limits | Constraints, dependencies, budget, invariants |
| 3 - Communication | Learning and exchange | Interfaces, naming, docs, coordination |
| 4 - Foundations | Roots and context | Existing architecture, history, hidden coupling |
| 5 - Creativity | Experimentation and play | Prototypes, UI choices, expressive design |
| 6 - Practice | Service and routine | Testing, quality, maintenance, workflow |
| 7 - Partnership | Others and contracts | Users, APIs, integrations, collaboration |
| 8 - Transformation | Risk and shared state | Migrations, secrets, permissions, deep refactors |
| 9 - Exploration | Principles and broad vision | Strategy, standards, research, long-term bets |
| 10 - Calling | Public outcome and reputation | Delivery, reliability, production readiness |
| 11 - Community | Groups and systems | Ecosystem fit, shared tooling, team impact |
| 12 - The Hidden | Blind spots and endings | Unknown risks, cleanup, deferred costs |

## Reading the Cards

### Step 1: Read Each House and Card File

For each house, read its house file. For each drawn card, read its meaning
file. Note both the upright and reversed meanings. Use whichever matches the
card's orientation in the draw.

The `In Technical Context` section in a card file is a starting translation,
not a replacement for the orientation. If that technical note sounds too
decisive for the card's reversed meaning, adapt it through the reversed text
instead of following the sentence literally.

### Step 2: Map to Context

Translate the card's archetypal meaning into the current technical situation:

**Major Arcana** represent big-picture forces:
- Architectural decisions, paradigm shifts, fundamental approaches
- These carry more interpretive weight

**Minor Arcana** represent practical details:
- **Wands** (fire): Action, initiative, creativity, velocity, building
- **Cups** (water): Collaboration, user experience, intuition, satisfaction
- **Swords** (air): Analysis, logic, debugging, cutting through complexity, hard truths
- **Pentacles** (earth): Quality, craft, reliability, testing, maintenance, tangible results

**Court Cards** can represent approaches or roles:
- **Page**: Learning, experimenting, prototyping, beginner's mind
- **Knight**: Focused pursuit, rapid movement, single-minded effort
- **Queen**: Mastery with empathy, nurturing growth, mature judgment
- **King**: Authority, established patterns, proven approaches

When the task resembles a specialized skill workflow, choose the relevant lens
from `TECHNICAL_CONTEXT_LENSES.md` before deciding what action the reading
supports. This keeps the reading grounded in the actual mode of work: audit
pipeline stage, evidence type, technical domain, failure class, or stakeholder
coordination.

### Step 3: Synthesize the Story

Read all 12 houses as a narrative:

1. "The beginning stance is [House 1]..."
2. "The available resources and constraints are [House 2]..."
3. "The communication or interface concern is [House 3]..."
4. "The foundation or hidden dependency is [House 4]..."
5. "The creative opening is [House 5]..."
6. "The quality and maintenance requirement is [House 6]..."
7. "The integration or collaboration point is [House 7]..."
8. "The transformation or risk is [House 8]..."
9. "The guiding principle is [House 9]..."
10. "The delivery target is [House 10]..."
11. "The ecosystem or team impact is [House 11]..."
12. "The blind spot or closure is [House 12]..."

When time is tight, prioritize House 1 for the initial stance, House 6 for
execution quality, House 8 for risk, House 10 for delivery, and House 12 for
blind spots.

### Step 4: Make a Decision

The reading should bias you toward one of the viable approaches. State:
- Which approach the reading supports
- How specific cards influenced the choice
- What the reading suggests you should watch out for

For vulnerability discovery and correctness verification, the decision should
be about where to investigate next or which hypothesis to test. The reading can
prioritize attention, but it cannot prove safety, dismiss a finding, or replace
reproduction, testing, formal reasoning, or source-level evidence.

## Reversed Cards

Reversed cards don't mean "bad." They indicate:
- The energy is internalized rather than expressed
- The quality is blocked, delayed, or needs extra attention
- An alternative or inverted interpretation applies
- Shadow aspects of the card's theme

## Special Patterns

The 12-house spread deals 12 Major Arcana, 24 Minor Arcana, and an
independent reversal flag per card. The patterns below are calibrated to those
baselines (one Major per house is guaranteed, so "multiple Majors" is not a
signal in this spread).

### Heavy Reversal Count
The spread averages 18 reversed cards out of 36. If 24 or more are reversed
(roughly the top 3% of draws), the reading is telling you that many
things are blocked, inverted, or shadowed. Step back and reconsider the
assumptions driving the work before proceeding.

### Heavy Minor Suit Concentration
Each Minor suit is expected to contribute about 6 of the 24 Minor draws. If
one suit contributes 10 or more, the reading carries that suit's thematic
emphasis across many houses:
- Heavy Wands: Focus on action, momentum, and creative drive
- Heavy Cups: Focus on user needs, team dynamics, and emotional state
- Heavy Swords: Focus on analysis, conflict, and clear thinking
- Heavy Pentacles: Focus on craft, resources, and practical quality

### Weighty Majors in Critical Houses
Death, The Tower, The Devil, Judgement, or The World landing in House 1
(Self), House 8 (Transformation), or House 12 (The Hidden) amplifies themes
of identity, deep change, or unseen factors. Treat these as cues to slow
down and investigate before committing.

### Court Cards Clustering in People Houses
Court cards (Page, Knight, Queen, King) appearing in Houses 3 (Communication),
7 (Partnership), or 11 (Community) reinforce a people-oriented reading: the
work hinges on collaboration, contracts, or social dynamics rather than purely
technical execution.

## What the Reading Is NOT

- Not a substitute for requirements gathering when requirements are gettable
- Not permission to ignore best practices
- Not evidence that a security or correctness concern is real or false
- Not a way to avoid thinking critically
- Not deterministic (it's entropy, that's the point)

The reading adds a creative nudge to break analysis paralysis. The cards don't make the decision; they give you a direction to explore when you otherwise have none.
