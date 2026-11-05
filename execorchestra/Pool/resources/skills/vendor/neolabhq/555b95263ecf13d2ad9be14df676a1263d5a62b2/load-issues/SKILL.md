---
name: load-issues
description: Load all open issues from GitHub and save them as markdown files
argument-hint: None required - loads all open issues automatically
allowed-tools: Bash(gh issue:*), Bash(mkdir:*), Write
---

Load all open issues from the current GitHub repository and save them as markdown files in the `./specs/issues/` directory.

Follow these steps:

1. Use the gh CLI to list all open issues in the current repository:
   - Run `gh issue list --limit 100` to get all open issues

2. For each open issue, fetch detailed information:
   - Run `gh issue view <number> --json number,title,body,state,createdAt,updatedAt,author,labels,assignees,url`
   - Extract all relevant metadata

3. Create the issues directory:
   - Run `mkdir -p ./specs/issues` to ensure the directory exists

4. Save each issue as a separate markdown file:
   - File naming pattern: `<number-padded-to-3-digits>-<kebab-case-title>.md`
   - Example: `007-make-code-review-trigger-on-sql-sh-changes.md`

5. Use the following markdown template for each issue file:

```markdown
# Issue #<number>: <title>

**Status:** <state>
**Created:** <createdAt>
**Updated:** <updatedAt>
**Author:** <author.name> (@<author.login>)
**URL:** <url>

## Description

<body>

## Labels

<labels or "None">

## Assignees

<assignees or "None">
```

6. After all issues are saved, provide a summary of:
   - Total number of issues loaded
   - List of created files with their issue numbers and titles

IMPORTANT: Execute all steps in the correct order and ensure all issue data is properly formatted in the markdown files.
