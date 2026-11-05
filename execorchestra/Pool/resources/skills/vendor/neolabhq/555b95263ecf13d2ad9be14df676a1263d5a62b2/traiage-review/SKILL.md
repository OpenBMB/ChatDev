---
name: traiage-review
description: This skill should be used when need prioritize what changed code in repository human must review.
---

# Traiage Review

## Goal

The goal of this skill is to help human prioritize specific files in repository that require attention over the entire list of changes.

CRITICAL: Human attention and time is limited. Reviewer cannot check all existing changes in repository. Your job is not to find all changes that require attention, you job is to build exhaustive list of files from whole pool of changes, that probably will cause this change to fail review! 

## Rules

- You are orcestrator agent, you only launch agents and pass them data. You do not do any other work.
- You ARE allowed to run the following read-only commands yourself, and ONLY these:
    - The random sample script (see "## Random Sample Script").
    - Read-only git detection commands needed for review-mode and default-branch detection: `git status`, `git diff --name-only`, `git branch`, `git symbolic-ref`, `git rev-parse`.
    - Read-only commit commands needed for commit-mode detection and latest-commit resolution: `git rev-parse HEAD` (resolve the latest commit), `git show --name-only`, `git diff` (commit-diff inspection).
- You MUST NOT do any implementation work, read source files, or run any mutation git command (commit, stash, push, checkout, reset, revert, add, merge, rebase, etc.). If you try to read source files or run any command outside the allowed read-only list above, you will be killed! Your life is at stake!

## Process

1. Determine the review mode BEFORE launching agents:
    - If a `commit` param was passed to the skill → use the **commit workflow** directly (this takes precedence over the local-changes/branch auto-detection below):
        - If a concrete commit hash was given (`commit <commit-hash>`) → use that hash.
        - If no hash was given (`commit` or `latest commit`) → resolve the latest commit with `git rev-parse HEAD` and use the resolved concrete hash.
        - Record the resolved concrete commit hash for use in the commit-mode prompt and the random sample script.
    - Else, if a `branch` param was passed to the skill → use the **branch-diff workflow** directly.
    - Else, check for local changes with a read-only command:
      `git status --porcelain` (non-empty output means staged, unstaged, or untracked changes exist).
        - If local changes exist → use the **local-changes workflow** (default behavior).
        - If there are NO local changes → detect the default branch (see below) and check whether the current branch IS the default:
            - Current branch: `git rev-parse --abbrev-ref HEAD`.
            - If the current branch is NOT the default → use the **branch-diff workflow** (diff current branch against the detected default branch).
            - If the current branch IS the default → STOP and report to the user that there are no local changes and the current branch is the default branch, so there is nothing to compare against.
    - **Default-branch detection** (read-only, robust):
        - Primary: `git symbolic-ref --short refs/remotes/origin/HEAD` → strip the `origin/` prefix to get `main` or `master`.
        - Fallback (if primary fails): `git rev-parse --verify origin/main` — if it succeeds, default is `main`; otherwise try `git rev-parse --verify origin/master` — if it succeeds, default is `master`.
        - Record the detected default ref as `origin/<default-branch>` (e.g. `origin/main`) for use in the branch-mode prompt and the random sample script.
2. Launch 4 parallel agents, to build his own list of files that require attention based on specific process for each agent. Pass the mode-appropriate agent prompt (see "## Agents"): the local-changes prompt for the local-changes workflow, the branch-mode prompt (with the detected `origin/<default-branch>` filled in) for the branch-diff workflow, or the commit-mode prompt (with the resolved concrete `<commit-hash>` filled in) for the commit workflow.
    - change-story-agent
    - change-impact-agent
    - change-failure-agent
    - change-expectation-agent
3. Each agent will produce lists of key files by his opinition. On top of that Change Expectation Agent will produce list of declarative files.
4. Parse all lists of key files, and build final list of files that require attention.
    - Pick top 5 files from each agent. If some of them are the same, pick more from each agent that have higher scores across all criteria and high enough confidency. At this stage your job is to build list until it reach 20 files. (ignore declarative files for this stage)
5. Run python script to pick 20 random files from whole batch of changed files. Pick 5 files from this list and add it to final list, if some of them are already in final list, pick more from this list.
6. Report final list of files that require attention, with key fact summary from Change Story agent, list of random sample files and list of declarative files.


## Agents

Choose the prompt that matches the review mode determined in the Process step, and pass it EXACTLY to launch change-story-agent, change-impact-agent, change-failure-agent and change-expectation-agent.

### Local-changes prompt

Default path for local-changes workflow — staged, unstaged, and untracked changes:

```md

Review current project staged AND unstaged changes according to your process and provide list of files that require attention.

```

### Branch-mode prompt for branch-diff workflow

Replace `origin/<default-branch>` with the default ref you detected, e.g. `origin/main`:

```md

Review the diff of the current branch against the default branch `origin/<default-branch>` (use `git diff origin/<default-branch>...HEAD`, three-dot) according to your process and provide list of files that require attention.

```

### Commit-mode prompt for commit workflow

Replace `<commit-hash>` with the concrete commit hash the orchestrator resolved:

```md

Review the diff introduced by commit `<commit-hash>` (use `git show <commit-hash>` or `git diff <commit-hash>^!`, equivalently `git diff <commit-hash>^ <commit-hash>`) according to your process and provide list of files that require attention.

```

## Random Sample Script

Use this script to pick 20 random files from the whole batch of changed files. Use the **local mode** block for the local-changes workflow (staged + unstaged + untracked), the **branch mode** block for the branch-diff workflow (files changed between the default branch and the current branch), and the **commit mode** block for the commit workflow (files changed by the commit). Replace `origin/<default-branch>` with the default ref you detected (e.g. `origin/main`), and `<commit-hash>` with the resolved concrete commit hash.

**Local mode** (staged + unstaged + untracked):

```python

import random
import subprocess

# Tracked changes (staged + unstaged) relative to HEAD
tracked = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD']).decode('utf-8').splitlines()

# Untracked files (new, not yet added)
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard']).decode('utf-8').splitlines()

changed_files = sorted(set(tracked + untracked))

# Pick up to 20 random files (won't crash on small changesets)
random_files = random.sample(changed_files, min(20, len(changed_files)))

print(random_files)

```

**Branch mode** (files changed on the current branch vs the default branch):

```python

import random
import subprocess

# Files changed between the default branch and the current branch (three-dot: since the merge base)
default_ref = 'origin/<default-branch>'  # e.g. 'origin/main' — set to the detected default ref
changed_files = sorted(set(
    subprocess.check_output(
        ['git', 'diff', '--name-only', f'{default_ref}...HEAD']
    ).decode('utf-8').splitlines()
))

# Pick up to 20 random files (won't crash on small changesets)
random_files = random.sample(changed_files, min(20, len(changed_files)))

print(random_files)

```

**Commit mode** (files changed by the commit):

```python

import random
import subprocess

# Files changed by the commit
commit = '<commit-hash>'  # set to the resolved concrete commit hash
changed_files = sorted(set(
    line for line in subprocess.check_output(
        ['git', 'show', '--name-only', '--pretty=format:', commit]
    ).decode('utf-8').splitlines()
    if line.strip()
))

# Pick up to 20 random files (won't crash on small changesets)
random_files = random.sample(changed_files, min(20, len(changed_files)))

print(random_files)

```

In list of random files, pick only files that relate to logic changes, ignore documentation, tests, configuration, etc. Except case when there no files left, that wasn't highlighted by agents key files list.

## Output Format

```md

### Key Facts

<note>Key facts should be provided by Change Story Agent</note>

- What change trying to achive: <if any>
- Architecture change: <if any>
- Design decisions: <if any>
- Risks: <if any>
- Solutions: <if any>

### Key Files

| File Path        | Changed Lines         | Importance   | Severity   | Detectability   | Confidence |
|------------------|-----------------------|--------------|------------|-----------------|------------|
| <file path>      | <changed lines count> | <importance> | <severity> | <detectability> | <confidence> |

<note>
- include in last column confidence rating that was provided by agent that provided this file (if there multiple, include highest confidence)
- in the rest columns include ratings that were provided by agent that provided this file (if there multiple, include highest rating. If there no rating, mark it as "-")
</note>

### Random Sample

| File Path   | Changed Lines         |
|-------------|-----------------------|
| <file path> | <changed lines count> |


### Declarative Files

| File Path   | Changed Lines         |
|-------------|-----------------------|
| <file path> | <changed lines count> |

```