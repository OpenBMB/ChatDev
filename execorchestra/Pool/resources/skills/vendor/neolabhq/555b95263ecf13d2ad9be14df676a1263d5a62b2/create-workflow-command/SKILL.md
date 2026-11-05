---
name: create-workflow-command
description: Create a workflow command that orchestrates multi-step execution through sub-agents with file-based task prompts
argument-hint: "[workflow-name] [description]"
allowed-tools: Read, Write, Glob, Grep, Bash(mkdir:*)
---

# Create Workflow Command

Create a command that orchestrates multi-step workflows by dispatching sub-agents with task-specific instructions stored in separate files.

## User Input

```text
Workflow Name: $1
Description: $2
```

## Architecture Overview

Workflow commands solve the **context bloat problem**: instead of embedding detailed step instructions in the main command (polluting orchestrator context), store them in separate task files that sub-agents read on-demand.

```
plugins/<plugin-name>/
├── commands/
│   └── <workflow>.md          # Lean orchestrator (~50-100 tokens per step)
├── agents/                     # Optional: reusable executor agents
│   └── step-executor.md       # Custom agent with specific tools/behavior
└── tasks/                      # All task instructions directly here
    ├── step-1-<name>.md       # Full instructions (~500+ tokens each)
    ├── step-2-<name>.md
    ├── step-3-<name>.md
    └── common-context.md      # Shared context across workflows
```

## Key Principles

### 1. Context Isolation

Each sub-agent gets its own isolated context window. The main orchestrator stays lean while sub-agents load detailed instructions from files.

| Component | Context Cost | Purpose |
|-----------|--------------|---------|
| Orchestrator command | ~50-100 tokens/step | Dispatch and coordinate |
| Task file | ~500+ tokens | Detailed step instructions |
| Sub-agent base | ~294 tokens | System prompt overhead |

### 2. Sub-Agent Capabilities

Sub-agents spawned via Task tool:

| Capability | Available | Notes |
|------------|-----------|-------|
| Read tool | ✅ Yes | Can read any file |
| Write tool | ✅ Yes | If not restricted |
| Grep/Glob | ✅ Yes | For code search |
| Skills loading | ❌ No | Skills don't auto-load in sub-agents |
| Spawn sub-agents | ❌ No | Cannot nest Task tool |
| Resume context | ✅ Yes | Via `resume` parameter |

### 3. File Reference Pattern

Use `${CLAUDE_PLUGIN_ROOT}` for portable paths within plugin:

```markdown
Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-1-workflow-name.md and execute.
```

Sub-agent will use Read tool to fetch the file content.

## Implementation Process

### Step 1: Gather Requirements

Ask user (if not provided):

1. **Workflow name**: kebab-case identifier (e.g., `feature-implementation`)
2. **Description**: What the workflow accomplishes
3. **Steps**: List of discrete steps with:
   - Step name
   - Step goal
   - Required tools
   - Expected output
4. **Execution mode**: Sequential or parallel steps
5. **Agent type**: `general-purpose` or custom agent

### Step 2: Create Directory Structure

```bash
# Create tasks directory (if it doesn't exist)
mkdir -p ${CLAUDE_PLUGIN_ROOT}/tasks

# Optional: Create agents directory (if using custom agents)
mkdir -p ${CLAUDE_PLUGIN_ROOT}/agents
```

**Note**: All task files (both workflow-specific steps and shared context) are placed directly in `tasks/` without subdirectories.

### Step 3: Create Task Files

For each step, create a task file with this structure:

```markdown
# Step N: <Step Name>

## Context
You are executing step N of the <workflow-name> workflow.

## Goal
<Clear, specific goal for this step>

## Input
<What this step receives from previous steps or user>

## Instructions
1. <Specific action>
2. <Specific action>
3. <Specific action>

## Constraints
- <Limitation or boundary>
- <What NOT to do>

## Expected Output
<What to return to orchestrator>

## Success Criteria
- [ ] <Measurable outcome>
- [ ] <Measurable outcome>
```

### Step 4: Create Orchestrator Command

Create the main command file with this pattern:

```markdown
---
description: <Workflow description>
argument-hint: <Required arguments>
allowed-tools: Task, Read
model: sonnet
---

# <Workflow Name>

## User Input

\`\`\`text
$ARGUMENTS
\`\`\`

## Workflow Execution

### Step 1: <Step Name>

Launch general-purpose agent:
- **Description**: "<3-5 word summary>"
- **Prompt**:
  \`\`\`
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-1-<workflow>-<name>.md and execute.

  Context:
  - TARGET: $1
  - MODE: $2
  \`\`\`

**Capture**: <What to extract from result>

### Step 2: <Step Name>

Launch general-purpose agent:
- **Description**: "<3-5 word summary>"
- **Prompt**:
  \`\`\`
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-2-<workflow>-<name>.md and execute.

  Context from Step 1:
  - <Key data from previous step>
  \`\`\`

### Step 3: <Step Name>

[Continue pattern...]

## Completion

Summarize workflow results:
1. <What was accomplished>
2. <Key outputs>
3. <Next steps if any>
```

#### Frontmatter Options

| Field | Purpose | Default |
|-------|---------|---------|
| `description` | Brief description of workflow purpose | Required |
| `argument-hint` | Expected arguments description | None |
| `allowed-tools` | Tools the command can use | Inherits from conversation |
| `model` | Specific Claude model (sonnet, opus, haiku) | Inherits from conversation |

**Model selection**:
- `haiku` - Fast, efficient for simple workflows
- `sonnet` - Balanced performance (recommended default)
- `opus` - Maximum capability for complex orchestration

## Execution Patterns

### Pattern A: Sequential Steps (Default)

Each step depends on previous step's output:

```markdown
### Step 1: Analyze
Launch agent → Get analysis result

### Step 2: Plan (uses Step 1 result)
Launch agent with Step 1 context → Get plan

### Step 3: Execute (uses Step 2 result)
Launch agent with Step 2 context → Complete
```

### Pattern B: Parallel Independent Steps

Steps can run concurrently:

```markdown
### Analysis Phase (Parallel)

Launch 3 agents simultaneously:
1. Agent 1: Security analysis → Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-1a-security.md
2. Agent 2: Performance analysis → Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-1b-performance.md
3. Agent 3: Code quality analysis → Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-1c-quality.md

**Wait for all**, then consolidate results.

### Synthesis Phase
Launch agent with all analysis results...
```

### Pattern C: Stateful Multi-Step (Resume)

When steps need shared context:

```markdown
### Step 1: Initialize
Launch agent, **capture agent_id**

### Step 2: Continue (same context)
Resume agent using agent_id:
- **resume**: <agent_id from Step 1>
- **prompt**: "Proceed to phase 2: <additional instructions>"
```

## Example: Feature Implementation Workflow

### Orchestrator Command

```markdown
---
description: Execute feature implementation through research, planning, and coding phases
argument-hint: [feature-description]
allowed-tools: Task, Read, TodoWrite
model: sonnet
---

# Implement Feature

## User Input
\`\`\`text
$ARGUMENTS
\`\`\`

Create TodoWrite with workflow steps.

## Phase 1: Research

Launch general-purpose agent:
- **Description**: "Research feature requirements"
- **Prompt**:
  \`\`\`
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-1-feature-impl-research.md

  Feature: $ARGUMENTS
  \`\`\`

**Extract**: Key findings, constraints, existing patterns

## Phase 2: Architecture

Launch general-purpose agent:
- **Description**: "Design feature architecture"
- **Prompt**:
  \`\`\`
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-2-feature-impl-architecture.md

  Feature: $ARGUMENTS
  Research findings: <summary from Phase 1>
  \`\`\`

**Extract**: File structure, components, interfaces

## Phase 3: Implementation

Launch developer agent:
- **Description**: "Implement feature code"
- **Prompt**:
  \`\`\`
  Read ${CLAUDE_PLUGIN_ROOT}/tasks/step-3-feature-impl-implement.md

  Architecture: <summary from Phase 2>
  \`\`\`

## Completion

Mark todos complete. Report:
1. Files created/modified
2. Tests added
3. Remaining work
```

### Task File Example (step-1-feature-impl-research.md)

```markdown
# Step 1: Feature Research

## Context
You are the research phase of a feature implementation workflow.

## Goal
Thoroughly understand the feature requirements and existing codebase context before any implementation begins.

## Instructions

1. **Parse Feature Request**
   - Extract core requirements
   - Identify acceptance criteria
   - Note any constraints mentioned

2. **Codebase Analysis**
   - Search for similar existing features
   - Identify relevant patterns and conventions
   - Find reusable components/utilities

3. **Dependency Check**
   - What existing code will this feature interact with?
   - Are there breaking change risks?
   - What tests exist for related functionality?

4. **Gap Analysis**
   - What's missing from the request?
   - What clarifications might be needed?
   - What edge cases should be considered?

## Constraints
- Do NOT write any implementation code
- Do NOT modify any files
- Focus purely on research and analysis

## Expected Output

Return a structured research summary:

\`\`\`markdown
## Feature Understanding
- Core requirement: <summary>
- Acceptance criteria: <list>

## Codebase Context
- Similar features: <list with file paths>
- Patterns to follow: <list>
- Reusable code: <list with file paths>

## Dependencies
- Files affected: <list>
- Tests to consider: <list>

## Open Questions
- <Question 1>
- <Question 2>

## Recommendation
<Brief recommendation for architecture phase>
\`\`\`

## Success Criteria
- [ ] Feature requirements clearly articulated
- [ ] Relevant existing code identified
- [ ] No implementation attempted
- [ ] Clear handoff to architecture phase
```

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No nested sub-agents | Sub-agents can't spawn Task tool | Keep all orchestration in main command |
| No skill auto-loading | Sub-agents don't trigger skills | Pass explicit file paths or inline context |
| Fresh context per agent | Each dispatch starts empty | Use resume pattern OR pass summaries |
| File read latency | Extra tool call per step | Acceptable trade-off for context savings |

## Validation Checklist

Before finalizing workflow command:

- [ ] Each step has clear, specific goal
- [ ] Task files are self-contained (sub-agent doesn't need external context)
- [ ] File paths use `${CLAUDE_PLUGIN_ROOT}` for portability
- [ ] Context passed between steps is minimal (summaries, not full data)
- [ ] Orchestrator command stays lean (<100 tokens per step dispatch)
- [ ] Error handling defined for step failures
- [ ] Success criteria measurable for each step

## Create the Workflow

Based on user input, create:

1. **Directories**:
   - `${CLAUDE_PLUGIN_ROOT}/tasks/` - All task files directly here
   - `${CLAUDE_PLUGIN_ROOT}/agents/` - (Optional) Custom agent definitions

2. **Task files**: Create in `tasks/` directory with naming pattern `step-N-<workflow>-<name>.md`
   - Example: `step-1-feature-impl-research.md`
   - Example: `step-2-feature-impl-architecture.md`
   - Shared context: `common-context.md` directly in `tasks/`

3. **Orchestrator command**: Lean dispatch logic in `commands/<workflow-name>.md`

4. **Custom agents** (Optional): If workflow needs specialized agent behavior in `agents/`

5. **Update plugin.json**: Add command to plugin manifest if needed

After creation, suggest testing with `/customaize-agent:test-prompt` command.
