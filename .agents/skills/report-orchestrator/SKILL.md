---
name: report-orchestrator
description: Manage a long-form report with the built-in report tools, keeping chapters structured and revision-friendly.
allowed-tools:
  - report_read
  - report_read_chapter
  - report_outline
  - report_create_chapter
  - report_rewrite_chapter
  - report_continue_chapter
  - report_reorder_chapters
  - report_del_chapter
  - report_export_pdf
---

# Report Orchestrator

Use this skill when a task needs a report that evolves over multiple steps or review loops.

This skill is intended for:
- chapter-by-chapter report drafting
- review-driven rewrites
- preserving report structure while iterating
- exporting a final PDF once the report is approved

Requirements:
- The agent should have access to the built-in `report_*` tools.

Workflow:
1. Activate this skill when the task produces a structured report instead of a one-shot answer.
2. Inspect the current outline before editing.
3. Operate one chapter at a time unless the user explicitly wants a full rewrite.
4. Use report tools to create, rewrite, continue, reorder, or delete chapters.
5. Export the PDF only when the report is clearly complete.

Rules:
1. Keep chapter titles stable unless there is a reason to rename them.
2. Prefer surgical edits over rewriting the entire report.
3. When changing order, explain why the new sequence is stronger.

Expected output shape:
- Current report state
- Actions taken
- Remaining gaps
- Whether export is ready
