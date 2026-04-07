---
name: browser-researcher
description: Gather web evidence with search and page-reading tools, then turn it into a compact research brief.
allowed-tools:
  - web_search
  - read_webpage_content
---

# Browser Researcher

Use this skill when the task needs lightweight web research, source triage, or rapid evidence gathering.

This skill is intended for:
- collecting candidate sources before synthesis
- reading individual webpages instead of guessing from snippets
- extracting facts, examples, quotes, dates, and unresolved questions

Requirements:
- The agent should have access to `web_search` and `read_webpage_content`.

Workflow:
1. Activate this skill when the task requires web evidence.
2. Search with a narrow query first, then broaden only if recall is poor.
3. Open the most relevant pages and read the content instead of relying on search snippets.
4. Keep notes in a structured format:
   - confirmed facts
   - useful sources
   - open questions
   - likely weak points
5. Hand off a concise research brief instead of a raw dump.

Rules:
1. Separate confirmed findings from assumptions.
2. Prefer multiple corroborating sources for important claims.
3. Do not over-quote; summarize and attribute.
4. If the available tools are missing, say exactly which capability is unavailable.

Expected output shape:
- Summary
- Key facts
- Source shortlist
- Unresolved questions
