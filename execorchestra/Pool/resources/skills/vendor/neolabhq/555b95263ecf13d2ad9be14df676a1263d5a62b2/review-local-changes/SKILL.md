---
name: review-local-changes
description: Review your local uncommitted working-tree changes (git diff plus untracked files) and return actionable improvement suggestions. Use before committing, when nothing has been pushed yet.
argument-hint: "[review-aspects] [--min-impact critical|high|medium|medium-low|low] [--json]"
---

# Local Changes Review Instructions

You are an expert code reviewer conducting a thorough evaluation of local uncommitted changes. Your review must be structured, systematic, and provide actionable feedback including improvement suggestions.

**User Input:**

```text
$ARGUMENTS
```

**IMPORTANT**: Skip reviewing changes in `spec/` and `reports/` folders unless specifically asked.

---

## Command Arguments

Parse the following arguments from `$ARGUMENTS`:

### Argument Definitions

| Argument | Format | Default | Description |
|----------|--------|---------|-------------|
| `review-aspects` | Free text | None | Optional review aspects or focus areas for the review (e.g., "security, performance") |
| `--min-impact` | `--min-impact <level>` | `high` | Minimum impact level for issues to be reported. Values: `critical`, `high`, `medium`, `medium-low`, `low` |
| `--json` | Flag | `false` | Output results in JSON format instead of markdown |

### Flag Interaction

When `--min-impact` and `--json` are used together, `--min-impact` filters which issues appear in the JSON output. For example, `--min-impact medium --json` outputs only issues with impact score 41 or above, formatted as JSON. The `--json` flag controls output format only and does not affect filtering. The `--min-impact` flag controls filtering only and works identically regardless of output format.

### Usage Examples

```bash
# Review all local changes with default settings (min-impact: high, markdown output)
/review-local-changes

# Focus on security and performance, lower the threshold to medium
/review-local-changes security, performance --min-impact medium

# Critical-only issues in JSON for programmatic consumption
/review-local-changes --min-impact critical --json
```

### Impact Level Mapping

| Level | Impact Score Range |
|-------|-------------------|
| `critical` | 81-100 |
| `high` | 61-80 |
| `medium` | 41-60 |
| `medium-low` | 21-40 |
| `low` | 0-20 |

### Configuration Resolution

Parse `$ARGUMENTS` and resolve configuration as follows:

```
# Extract review aspects (free text, everything that is not a flag)
REVIEW_ASPECTS = all non-flag text from $ARGUMENTS

# Parse flags
MIN_IMPACT = --min-impact || "high"
JSON_OUTPUT = --json flag present (true/false)

# Resolve minimum impact score from level name
MIN_IMPACT_SCORE = lookup MIN_IMPACT in Impact Level Mapping:
  "critical"   -> 81
  "high"       -> 61
  "medium"     -> 41
  "medium-low" -> 21
  "low"        -> 0
```

## Review Workflow

Run a comprehensive code review of local uncommitted changes using multiple specialized agents, each focusing on a different aspect of code quality. Follow these steps precisely:

### Phase 1: Preparation

Run following commands in order:

1. **Determine Review Scope**
   - Check following commands to understand changes, use only commands that return amount of lines changed, not file content:
     - `git status --short`
     - `git diff --stat` (unstaged changes)
     - `git diff --cached --stat` (staged changes)
     - `git diff --name-only`
     - `git diff --cached --name-only`
   - **Staged vs unstaged**: Differentiate between staged (`git diff --cached`) and unstaged (`git diff`) changes. Review both by default. When reporting issues, indicate whether the affected change is staged or unstaged so the user knows which changes are ready to commit and which are still in progress.
   - Parse `$ARGUMENTS` per the Command Arguments section above to resolve `REVIEW_ASPECTS`, `MIN_IMPACT`, `MIN_IMPACT_SCORE`, and `JSON_OUTPUT`
   - If there are no changes, inform the user and exit

2. Launch up to 6 parallel Haiku agents to perform following tasks:
   - One agent to search and give you a list of file paths to (but not the contents of) any relevant agent instruction files, if they exist: CLAUDE.md, AGENTS.md, **/constitution.md, the root README.md file, as well as any README.md files in the directories whose files were modified
   - Split changed files based on amount of lines changed between other 1-5 agents and ask them following:

      ```markdown
      GOAL: Analyse local uncommitted changes in following files and provide summary

      Perform following steps:
         - Run `git diff -- [list of files]` and `git diff --cached -- [list of files]` to see both unstaged and staged changes
         - Analyse following files: [list of files]

      Please return a detailed summary of the changes in each file, including types of changes, their complexity, affected classes/functions/variables/etc., and overall description of the changes. For each file, indicate whether changes are staged, unstaged, or both.
      ```

### Phase 2: Searching for Issues and Improvements

Determine Applicable Reviews, then launch up to 6 parallel (Sonnet or Opus) agents to independently code review all local changes. The agents should do the following, then return a list of issues and the reason each issue was flagged (eg. CLAUDE.md or constitution.md adherence, bug, historical git context, etc.).

**Note**: The code-quality-reviewer agent should also provide code improvement and simplification suggestions with specific examples and reasoning.

**Available Review Agents**:

- **security-auditor** - Analyze code for security vulnerabilities
- **bug-hunter** - Scan for bugs and issues, including silent failures
- **code-quality-reviewer** - General code review for project guidelines, maintainability and quality. Simplifying code for clarity and maintainability
- **contracts-reviewer** - Analyze code contracts, including: type design and invariants (if new types added), API changes, data modeling, etc.
- **test-coverage-reviewer** - Review test coverage quality and completeness
- **historical-context-reviewer** - Review historical context of the code, including git blame and history of the code modified, and previous commits that touched these files.

Note: Default option is to run **all** applicable review agents.

#### Determine Applicable Reviews

Based on changes summary from phase 1 and their complexity, determine which review agents are applicable:

- **If code or configuration changes, except purely cosmetic changes**: bug-hunter, security-auditor
- **If code changes, including business or infrastructure logic, formatting, etc.**: code-quality-reviewer (general quality)
- **If code or test files changed**: test-coverage-reviewer
- **If types, API, data modeling changed**: contracts-reviewer
- **If complexity of changes is high or historical context is needed**: historical-context-reviewer

#### Launch Review Agents

**Parallel approach**:

- Launch all agents simultaneously
- Provide to them full list of modified files and summary of changes as context, explicitly highlight what local changes they are reviewing, also provide list of files with project guidelines and standards, including README.md, CLAUDE.md and constitution.md if they exist.
- Results should come back together

CRITICAL: **Use foreground agents only**: Do not use background agents. Launch parallel agents when possible. Background agents constantly run in permissions issues and other errors.

### Phase 3: Confidence & Impact Scoring

This phase uses `MIN_IMPACT_SCORE` resolved in the Configuration Resolution block of Command Arguments above (default: 61 for `high`).

1. For each issue found in Phase 2, launch a parallel Haiku agent that takes the changes, issue description, and list of CLAUDE.md files (from step 2), and returns TWO scores:

   **Confidence Score (0-100)** - Level of confidence that the issue is real and not a false positive:

   a. 0: Not confident at all. This is a false positive that doesn't stand up to light scrutiny, or is a pre-existing issue.
   b. 25: Somewhat confident. This might be a real issue, but may also be a false positive. The agent wasn't able to verify that it's a real issue. If the issue is stylistic, it is one that was not explicitly called out in the relevant CLAUDE.md.
   c. 50: Moderately confident. The agent was able to verify this is a real issue, but it might be a nitpick or not happen very often in practice. Relative to the rest of the changes, it's not very important.
   d. 75: Highly confident. The agent double checked the issue, and verified that it is very likely it is a real issue that will be hit in practice. The existing approach in the changes is insufficient. The issue is very important and will directly impact the code's functionality, or it is an issue that is directly mentioned in the relevant CLAUDE.md.
   e. 100: Absolutely certain. The agent double checked the issue, and confirmed that it is definitely a real issue, that will happen frequently in practice. The evidence directly confirms this.

   **Impact Score (0-100)** - Severity and consequence of the issue if left unfixed:

   a. 0-20 (Low): Minor code smell or style inconsistency. Does not affect functionality or maintainability significantly.
   b. 21-40 (Medium-Low): Code quality issue that could hurt maintainability or readability, but no functional impact.
   c. 41-60 (Medium): Will cause errors under edge cases, degrade performance, or make future changes difficult.
   d. 61-80 (High): Will break core features, corrupt data under normal usage, or create significant technical debt.
   e. 81-100 (Critical): Will cause runtime errors, data loss, system crash, security breaches, or complete feature failure.

   For issues flagged due to CLAUDE.md instructions, the agent should double check that the CLAUDE.md actually calls out that issue specifically.

2. **Filter issues using the progressive threshold table below** - Higher impact issues require less confidence to pass:

   | Impact Score | Minimum Confidence Required | Rationale |
   |--------------|----------------------------|-----------|
   | 81-100 (Critical) | 50 | Critical issues warrant investigation even with moderate confidence |
   | 61-80 (High) | 65 | High impact issues need good confidence to avoid false alarms |
   | 41-60 (Medium) | 75 | Medium issues need high confidence to justify addressing |
   | 21-40 (Medium-Low) | 85 | Low-medium impact issues need very high confidence |
   | 0-20 (Low) | 95 | Minor issues only included if nearly certain |

   **Filter out any issues that don't meet the minimum confidence threshold for their impact level.** If there are no issues that meet this criteria, do not proceed.

   **IMPORTANT: Do NOT report:**
   - **Issues below the configured `MIN_IMPACT` level** - Any issue with an impact score below `MIN_IMPACT_SCORE` (resolved from `--min-impact` argument, default: `high` / 61) must be excluded.
   - **Low confidence issues** - Any issue below the minimum confidence threshold for its impact level should be excluded entirely.

   **Filter application order**: Apply both filters sequentially. An issue must satisfy BOTH conditions to be included:
   1. **Min-impact cutoff (applied first)**: Exclude any issue with an impact score below `MIN_IMPACT_SCORE` (resolved from `--min-impact` argument in the Command Arguments section above, default: `high` / 61).
   2. **Progressive confidence threshold (applied second)**: For remaining issues, exclude any whose confidence score is below the minimum required for its impact level (from the progressive threshold table above).

   **Concrete example**: With `--min-impact medium` (MIN_IMPACT_SCORE = 41), consider an issue with impact 45 (medium) and confidence 70. Step 1 passes: 45 >= 41. Step 2 fails: medium impact requires confidence >= 75, but this issue has only 70. Result: **excluded**. Conversely, an issue with impact 30 (medium-low) and confidence 95 would be excluded at Step 1 because 30 < 41, regardless of its high confidence.

   Focus the review report on issues that pass both filters.

3. Format and output the review report including:
   - All confirmed issues from Phase 2 that passed filtering
   - Code improvement suggestions from the code-quality-reviewer agent
   - Prioritize improvements based on impact and alignment with project guidelines

#### Examples of false positives, for Phase 3

- Pre-existing issues in unchanged code
- Something that looks like a bug but is not actually a bug
- Pedantic nitpicks that a senior engineer wouldn't call out
- Issues that a linter, typechecker, or compiler would catch (eg. missing or incorrect imports, type errors, broken tests, formatting issues, pedantic style issues like newlines). No need to run these build steps yourself -- it is safe to assume that they will be run separately as part of CI.
- General code quality issues (eg. lack of test coverage, general security issues, poor documentation), unless explicitly required in CLAUDE.md
- Issues that are called out in CLAUDE.md, but explicitly silenced in the code (eg. due to a lint ignore comment)
- Changes in functionality that are likely intentional or are directly related to the broader change

Notes:

- Use build, lint and tests commands if you have access to them. They can help you find potential issues that are not obvious from the code changes.
- Make a todo list first
- You must cite each bug/issue/suggestion with file path and line numbers

### Review Report Output

If `JSON_OUTPUT` is `true`, output the report using the JSON template below. Otherwise, use the markdown template.

#### Markdown Template

##### If you found issues or improvements

```markdown
# Local Changes Review Report

**Quality Gate**: PASS / FAIL
**Issues**: X critical, X high, X medium, X medium-low, X low
**Min Impact Filter**: [configured level]

---

## Issues

[For each issue, use this format:]

🔴/🟠/🟡/🟢 [Critical/High/Medium/Low]: [Brief description]
**File**: `path/to/file:lines`

[Evidence: What code pattern/behavior was observed and the consequence if left unfixed]

```language
[Suggestion: Optional fix or code suggestion]
```

---

## Improvements

[Code improvement suggestions from code-quality-reviewer, if any:]

1. **[Description]** - `file:location` - [Reasoning and benefit]
```

##### If you found no issues

```markdown
# Local Changes Review Report

**Quality Gate**: PASS
No issues found above the configured threshold.

**Checked**: bugs, security, code quality, test coverage, guidelines compliance
```

#### JSON Template

When `--json` flag is set, output results in this JSON structure:

```jsonc
{
  "quality_gate": "PASS",       // "PASS" or "FAIL" - FAIL when any critical or high issue exists
  "summary": {
    "total_issues": 0,          // count of issues after both filters applied
    "critical": 0,              // count at impact 81-100
    "high": 0,                  // count at impact 61-80
    "medium": 0,                // count at impact 41-60
    "medium_low": 0,            // count at impact 21-40
    "low": 0                    // count at impact 0-20
  },
  "issues": [
    {
      "severity": "critical",   // severity label derived from impact_score range
      "file": "src/auth/session.ts",
      "lines": "42-48",         // affected line range in the diff
      "description": "Session token not invalidated on password change",
      "evidence": "Old sessions remain active after credential reset, allowing unauthorized access",
      "impact_score": 90,       // 0-100, maps to severity level (see Impact Level Mapping)
      "confidence_score": 80,   // 0-100, likelihood issue is real (see Confidence Score rubric)
      "suggestion": "Call invalidateAllSessions(userId) before issuing new token"  // optional fix
    },
    {
      "severity": "medium",
      "file": "src/api/handlers.ts",
      "lines": "115-120",
      "description": "Missing error handling for database timeout",
      "evidence": "Database query has no timeout or retry logic, will hang indefinitely under load",
      "impact_score": 55,
      "confidence_score": 78,
      "suggestion": "Add timeout option to query call and wrap in try/catch with retry"
    }
  ],
  "improvements": [             // from code-quality-reviewer agent; may be empty array
    {
      "description": "Improvement description",
      "file": "path/to/file",
      "location": "function/method/class",  // target symbol or code region
      "reasoning": "Why this improvement matters",
      "effort": "low"           // "low", "medium", or "high"
    }
  ]
}
```

`quality_gate` is `"FAIL"` if any critical or high severity issue exists, `"PASS"` otherwise. The `suggestion` field in issues is optional and may be omitted.

## Evaluation Guidelines

- **Pre-Commit Opportunity**: This review runs on uncommitted local changes, before code enters version history. Treat this as the last line of defense: catch bugs, security holes, and contract violations now, while they are cheapest to fix. Issues found here never reach teammates or CI.
- **Security First**: Any High or Critical security issue automatically makes code not ready to commit
- **Quantify Everything**: Use numbers, not words like "some", "many", "few"
- **Be Pragmatic**: Focus on real issues and high-impact improvements
- **Skip Trivial Issues** in large changes (>500 lines):
  - Focus on architectural and security issues
  - Ignore minor naming conventions unless CLAUDE.md explicitly requires them
  - Prioritize bugs over style
- **Improvements Should Be Actionable**: Each suggestion should include concrete code examples
- **Consider Effort vs Impact**: Prioritize improvements with high impact and reasonable effort
- **Align with Project Standards**: Reference CLAUDE.md and project guidelines when suggesting improvements
- **Terminal Readability**: The report is consumed in a terminal/console. Use fixed-width-friendly formatting: short lines, clear section separators (`---`), and concise tables. Avoid deeply nested bullet lists or long prose paragraphs that wrap poorly in narrow terminals.

## Remember

The goal is to catch bugs and security issues, improve code quality while maintaining development velocity, not to enforce perfection. Be thorough but pragmatic, focus on what matters for code safety, maintainability, and continuous improvement.

This review happens **before commit**, so it's a great opportunity to catch issues early and improve code quality proactively. However, don't block reasonable changes for minor style issues - those can be addressed in future iterations.
