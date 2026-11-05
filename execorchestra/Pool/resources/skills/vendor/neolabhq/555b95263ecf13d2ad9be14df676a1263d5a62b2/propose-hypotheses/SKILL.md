---
name: propose-hypotheses
description: Execute complete FPF cycle from hypothesis generation to decision
argument-hint: "[problem-statement]"
allowed-tools: Task, Read, Write, Bash, AskUserQuestion
---

# Propose Hypotheses Workflow

Execute the First Principles Framework (FPF) cycle: generate competing hypotheses, verify logic, validate evidence, audit trust, and produce a decision.

## User Input

```text
Problem Statement: $ARGUMENTS
```

## Workflow Execution

### Step 1a: Create Directory Structure (Main Agent)

Create `.fpf/` directory structure if it does not exist:

```bash
mkdir -p .fpf/{evidence,decisions,sessions,knowledge/{L0,L1,L2,invalid}}
touch .fpf/{evidence,decisions,sessions,knowledge/{L0,L1,L2,invalid}}/.gitkeep
```

**Postcondition**: `.fpf/` directory scaffold exists.

---

### Step 1b: Initialize Context (FPF Agent)

Launch fpf-agent with sonnet[1m] model:
- **Description**: "Initialize FPF context"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/init-context.md and execute.

  Problem Statement: $ARGUMENTS

  **Write**: Context summary to `.fpf/context.md`**
  ```

---

### Step 2: Generate Hypotheses (FPF Agent)

Launch fpf-agent with sonnet[1m] model:
- **Description**: "Generate L0 hypotheses"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/generate-hypotheses.md and execute.

  Problem Statement: $ARGUMENTS
  Context: <summary from Step 1b>

  **Write**: List of hypothesis IDs and titles to `.fpf/knowledge/L0/`

  Reply with summary table in markdown format:

    | ID | Title | Kind | Scope |
    |----|-------|------|-------|
    | ... | ... | ... | ... |
  ```

---

### Step 3: Present Summary (Main Agent)

1. Read all L0 hypothesis files from `.fpf/knowledge/L0/`
2. Present summary table from agent response.
3. Ask user: "Would you like to add any hypotheses of your own? (yes/no)"

---

### Step 4: Add User Hypothesis (FPF Agent, Conditional Loop)

**Condition**: User says yes to adding hypotheses.

Launch fpf-agent with sonnet[1m] model:
- **Description**: "Add user hypothesis"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/add-user-hypothesis.md and execute.

  User Hypothesis Description: <get from user>

  **Write**: User hypothesis to `.fpf/knowledge/L0/`
  ```

**Loop**: Return to Step 3 after hypothesis is added.

**Exit**: When user says no or declines to add more.

---

### Step 5: Verify Logic (Parallel Sub-Agents)

**Condition**: User finished adding hypotheses.

For EACH L0 hypothesis file in `.fpf/knowledge/L0/`, launch parallel fpf-agent with sonnet[1m] model:
- **Description**: "Verify hypothesis: <hypothesis-id>"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/verify-logic.md and execute.

  Hypothesis ID: <hypothesis-id>
  Hypothesis File: .fpf/knowledge/L0/<hypothesis-id>.md

  **Move**: After you complete verification, move the file to `.fpf/knowledge/L1/` or `.fpf/knowledge/invalid/`.
  ```

**Wait for all agents**, then check that files are moved to `.fpf/knowledge/L1/` or `.fpf/knowledge/invalid/`.

---

### Step 6: Validate Evidence (Parallel Sub-Agents)

For EACH L1 hypothesis file in `.fpf/knowledge/L1/`, launch parallel fpf-agent with sonnet[1m] model:
- **Description**: "Validate hypothesis: <hypothesis-id>"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/validate-evidence.md and execute.

  Hypothesis ID: <hypothesis-id>
  Hypothesis File: .fpf/knowledge/L1/<hypothesis-id>.md

  **Move**: After you complete validation, move the file to `.fpf/knowledge/L2/` or `.fpf/knowledge/invalid/`.
  ```

**Wait for all agents**, then check that files are moved to `.fpf/knowledge/L2/` or `.fpf/knowledge/invalid/`.

---

### Step 7: Audit Trust (Parallel Sub-Agents)

For EACH L2 hypothesis file in `.fpf/knowledge/L2/`, launch parallel fpf-agent with sonnet[1m] model:
- **Description**: "Audit trust: <hypothesis-id>"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/audit-trust.md and execute.

  Hypothesis ID: <hypothesis-id>
  Hypothesis File: .fpf/knowledge/L2/<hypothesis-id>.md

  **Write**: Audit report to `.fpf/evidence/audit-{hypothesis-id}-{YYYY-MM-DD}.md`

  **Reply**: with R_eff score and weakest link
  ```

**Wait for all agents**, then check that audit reports are created in `.fpf/evidence/`.

---

### Step 8: Make Decision (FPF Agent)

Launch fpf-agent with sonnet[1m] model:
- **Description**: "Create decision record"
- **Prompt**:
  ```
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/decide.md and execute.

  Problem Statement: $ARGUMENTS
  L2 Hypotheses Directory: .fpf/knowledge/L2/
  Audit Reports: .fpf/evidence/

  **Write**: Decision record to `.fpf/decisions/`

  **Reply**: with decision record summary in markdown format:

  | Hypothesis | R_eff | Weakest Link | Status |
  |------------|-------|--------------|--------|
  | ... | ... | ... | ... |

  **Recommended Decision**: <hypothesis title>

  **Rationale**: <brief explanation>
  ```

**Wait for agent**, then check that decision record is created in `.fpf/decisions/`.
---

### Step 9: Present Final Summary (Main Agent)

1. Read the DRR from `.fpf/decisions/`
2. Present results from agent response.
3. Present next steps:
   - Implement the selected hypothesis
   - Use `/fpf:status` to check FPF state
   - Use `/fpf:actualize` if codebase changes
4. Ask user if he agree with the decision, if not launch fpf-agent at step 8 with instruction to modify the decision as user wants.

---

## Completion

Workflow complete when:
- [ ] `.fpf/` directory structure exists
- [ ] Context recorded in `.fpf/context.md`
- [ ] Hypotheses generated, verified, validated, and audited
- [ ] DRR created in `.fpf/decisions/`
- [ ] Final summary presented to user

**Artifacts Created**:
- `.fpf/context.md` - Problem context
- `.fpf/knowledge/L0/*.md` - Initial hypotheses
- `.fpf/knowledge/L1/*.md` - Verified hypotheses
- `.fpf/knowledge/L2/*.md` - Validated hypotheses
- `.fpf/knowledge/invalid/*.md` - Rejected hypotheses
- `.fpf/evidence/*.md` - Evidence files
- `.fpf/decisions/*.md` - Design Rationale Record
