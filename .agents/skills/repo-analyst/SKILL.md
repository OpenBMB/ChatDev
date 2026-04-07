---
name: repo-analyst
description: Inspect a codebase with file and search tools, then explain architecture, hotspots, and likely edit targets.
allowed-tools:
  - describe_available_files
  - list_directory
  - read_file_segment
  - search_in_files
---

# Repo Analyst

Use this skill when the task is about understanding a repository before changing it.

This skill is useful for:
- finding the entrypoints for a feature
- tracing where configuration is defined and consumed
- locating risky files before a refactor
- summarizing architecture for a human reviewer

Requirements:
- The agent should have access to file inspection and search tools.

Workflow:
1. Activate this skill when the task involves an unfamiliar repository or module.
2. Start with high-level file discovery before diving into implementation details.
3. Use targeted searches to connect routes, services, config, and UI surfaces.
4. Summarize the repo in terms of:
   - entrypoints
   - critical files
   - cross-module dependencies
   - likely edit points
5. Prefer references to exact files over vague descriptions.

Rules:
1. Do not claim a file exists unless a tool call found it.
2. Keep architecture summaries short and actionable.
3. Surface uncertainty when the code path is ambiguous.

Expected output shape:
- Overview
- Key files
- Dependency flow
- Recommended edit targets
