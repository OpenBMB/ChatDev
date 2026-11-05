---
name: git-notes
description: Use when adding metadata to commits without changing history, tracking review status, test results, code quality annotations, or supplementing commit messages post-hoc - provides git notes commands and patterns for attaching non-invasive metadata to Git objects.
---

# Git Notes

## Overview

Git notes attach metadata to commits (or any Git object) without modifying the objects themselves. Notes are stored separately and displayed alongside commit messages.

**Core principle:** Add information to commits after creation without rewriting history.

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Notes ref** | Storage location, default `refs/notes/commits` |
| **Non-invasive** | Notes never modify SHA of original object |
| **Namespaces** | Use `--ref` for different note categories |
| **Display** | Notes appear in `git log` and `git show` output |

## Quick Reference

| Task | Command |
|------|---------|
| Add note | `git notes add -m "message" <sha>` |
| View note | `git notes show <sha>` |
| Append | `git notes append -m "message" <sha>` |
| Edit | `git notes edit <sha>` |
| Remove | `git notes remove <sha>` |
| Use namespace | `git notes --ref=<name> <command>` |
| Push notes | `git push origin refs/notes/<name>` |
| Fetch notes | `git fetch origin refs/notes/<name>:refs/notes/<name>` |
| Show in log | `git log --notes=<name>` |

For complete command reference, see `references/commands.md`.

## Essential Patterns

### Code Review Tracking

```bash
# Mark reviewed
git notes --ref=reviews add -m "Reviewed-by: Alice <alice@example.com>" abc1234

# View review status
git log --notes=reviews --oneline
```

### Sharing Notes

```bash
# Push to remote
git push origin refs/notes/reviews

# Fetch from remote
git fetch origin refs/notes/reviews:refs/notes/reviews
```

### Preserving Through Rebase

```bash
git config notes.rewrite.rebase true
git config notes.rewriteMode concatenate
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Notes not showing in log | Specify ref: `git log --notes=reviews` or configure `notes.displayRef` |
| Notes lost after rebase | Enable: `git config notes.rewrite.rebase true` |
| Notes not on remote | Push explicitly: `git push origin refs/notes/commits` |
| "Note already exists" error | Use `-f` to overwrite or `append` to add |

## Best Practices

| Practice | Rationale |
|----------|-----------|
| Use namespaces | Separate notes by purpose (reviews, testing, audit) |
| Be explicit about refs | Always specify `--ref` for non-default notes |
| Push notes explicitly | Document sharing procedures in team guidelines |
| Use append over add -f | Preserve note history when accumulating |
| Configure rewrite preservation | Run `git config notes.rewrite.rebase true` before rebasing |

# Git Notes Command Reference

Complete reference for all git notes commands and options.

## Basic Operations

### Add a Note

```bash
# Add note to current HEAD
git notes add -m "Reviewed by Alice"

# Add note to specific commit
git notes add -m "Tested on Linux" abc1234

# Add note from file
git notes add -F review-comments.txt abc1234

# Add note interactively (opens editor)
git notes add abc1234

# Overwrite existing note
git notes add -f -m "Updated review status" abc1234

# Add empty note
git notes add --allow-empty abc1234
```

### View Notes

```bash
# Show note for HEAD
git notes show

# Show note for specific commit
git notes show abc1234

# View commit with notes in log
git log --show-notes
git show abc1234

# List all notes
git notes list

# List note for specific object
git notes list abc1234
```

**Example output with notes:**

```
commit abc1234def567890
Author: Developer <dev@example.com>
Date:   Mon Jan 15 10:00:00 2024 +0000

    feat: implement user authentication

Notes:
    Reviewed by Alice
    Tested-by: CI Bot <ci@example.com>
```

### Append to Notes

```bash
# Append to existing note (creates if doesn't exist)
git notes append -m "Additional review comment" abc1234

# Append from file
git notes append -F more-comments.txt abc1234

# Append multiple messages
git notes append -m "Comment 1" -m "Comment 2" abc1234
```

### Edit Notes

```bash
# Edit note interactively (opens editor)
git notes edit abc1234

# Edit note for HEAD
git notes edit
```

### Remove Notes

```bash
# Remove note from HEAD
git notes remove

# Remove note from specific commit
git notes remove abc1234

# Remove notes from multiple commits
git notes remove abc1234 def5678 ghi9012

# Ignore missing notes (no error if note doesn't exist)
git notes remove --ignore-missing abc1234

# Remove notes via stdin (bulk removal)
echo "abc1234" | git notes remove --stdin
```

### Copy Notes

```bash
# Copy note from one commit to another
git notes copy abc1234 def5678

# Copy note to HEAD
git notes copy abc1234

# Force overwrite destination note
git notes copy -f abc1234 def5678

# Bulk copy via stdin (useful with rebase/cherry-pick)
echo "abc1234 def5678" | git notes copy --stdin
```

### Prune Notes

```bash
# Remove notes for objects that no longer exist
git notes prune

# Dry-run to see what would be pruned
git notes prune -n

# Verbose output
git notes prune -v
```

### Get Notes Reference

```bash
# Show current notes ref being used
git notes get-ref
```

## Using Multiple Namespaces

Notes can be organized into separate namespaces (refs) for different purposes.

### Specify Notes Ref

```bash
# Add note to specific namespace
git notes --ref=refs/notes/reviews add -m "Approved" abc1234

# Shorthand (refs/notes/ prefix is assumed)
git notes --ref=reviews add -m "Approved" abc1234

# View notes from specific namespace
git notes --ref=reviews show abc1234

# List notes in namespace
git notes --ref=reviews list
```

### Environment Variable

```bash
# Set default notes ref for session
export GIT_NOTES_REF=refs/notes/reviews
git notes add -m "Approved"

# View notes from environment ref
git notes show abc1234
```

### Display Multiple Namespaces

```bash
# Show specific notes namespace in log
git log --notes=reviews

# Show multiple namespaces
git log --notes=reviews --notes=testing

# Show all notes
git log --notes='*'

# Disable notes display
git log --no-notes
```

## Merging Notes

When notes exist in multiple refs or from different sources, they can be merged.

### Merge Notes Refs

```bash
# Merge notes from another ref into current
git notes merge refs/notes/other

# Merge with strategy
git notes merge -s union refs/notes/other
git notes merge -s ours refs/notes/other
git notes merge -s theirs refs/notes/other
git notes merge -s cat_sort_uniq refs/notes/other

# Quiet merge
git notes merge -q refs/notes/other

# Verbose merge
git notes merge -v refs/notes/other
```

### Merge Strategies

| Strategy | Behavior |
|----------|----------|
| `manual` | Interactive conflict resolution (default) |
| `ours` | Keep local note on conflict |
| `theirs` | Keep remote note on conflict |
| `union` | Concatenate both notes |
| `cat_sort_uniq` | Concatenate, sort lines, remove duplicates |

### Resolve Merge Conflicts

```bash
# After merge conflict with manual strategy
# Resolve conflicts in .git/NOTES_MERGE_WORKTREE/

# Commit resolved merge
git notes merge --commit

# Abort merge
git notes merge --abort
```

## Configuration Options

### Git Config

```bash
# Set default notes ref
git config notes.displayRef refs/notes/reviews

# Display multiple notes refs
git config --add notes.displayRef refs/notes/testing

# Set merge strategy for notes
git config notes.mergeStrategy union

# Set merge strategy for specific namespace
git config notes.reviews.mergeStrategy theirs

# Preserve notes during rebase
git config notes.rewrite.rebase true

# Preserve notes during amend
git config notes.rewrite.amend true

# Set rewrite mode
git config notes.rewriteMode concatenate
```

### Sample .gitconfig

```gitconfig
[notes]
    displayRef = refs/notes/reviews
    displayRef = refs/notes/testing
    mergeStrategy = union

[notes "reviews"]
    mergeStrategy = theirs

[notes.rewrite]
    rebase = true
    amend = true
```

## Workflow Examples

### Code Review Tracking

```bash
# Mark commit as reviewed
git notes --ref=reviews add -m "Reviewed-by: Alice <alice@example.com>" abc1234

# Add review comments
git notes --ref=reviews append -m "Consider extracting helper function" abc1234

# View review status
git log --notes=reviews --oneline

# Mark as approved
git notes --ref=reviews add -f -m "APPROVED by Alice" abc1234
```

### Test Results Annotation

```bash
# Record test pass
git notes --ref=testing add -m "Tests passed: 2024-01-15
Platform: Linux x64
Coverage: 85%" abc1234

# Record test failure
git notes --ref=testing add -m "FAILED: Integration tests
See: https://ci.example.com/build/123" def5678

# View test status across commits
git log --notes=testing --oneline
```

### Audit Trail

```bash
# Add audit note
git notes --ref=audit add -m "Security review: PASSED
Reviewer: Security Team
Date: 2024-01-15
Ticket: SEC-456" abc1234

# Query audit status
git log --notes=audit --grep="Security review"
```

### Sharing Notes

```bash
# Push notes to remote
git push origin refs/notes/reviews

# Fetch notes from remote
git fetch origin refs/notes/reviews:refs/notes/reviews

# Push all notes refs
git push origin 'refs/notes/*'

# Fetch all notes refs
git fetch origin 'refs/notes/*:refs/notes/*'
```

### Bulk Operations

```bash
# Add notes to all commits by author in date range
git log --format="%H" --author="Alice" --since="2024-01-01" | \
  while read sha; do
    git notes add -m "Author verified" "$sha"
  done

# Remove notes from range of commits
git log --format="%H" HEAD~10..HEAD | xargs git notes remove --ignore-missing
```
