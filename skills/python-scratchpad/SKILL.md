---
name: python-scratchpad
description: Use the existing Python execution tools as a scratchpad for calculations, data transformation, and quick script-based validation.
allowed-tools: execute_code
---

# Python Scratchpad

Use this skill when the task benefits from a short Python script instead of pure reasoning.

This skill is especially useful for:
- arithmetic and unit conversions
- validating regexes or parsing logic
- transforming JSON, CSV, or small text payloads
- checking assumptions with a small reproducible script

Requirements:
- The agent should have access to `execute_code`.

Workflow:
1. If the task needs computation or a repeatable transformation, activate this skill.
2. If you need examples, call `read_skill_file` for `references/examples.md`.
3. Write a short Python script for the exact task.
4. Prefer `run_python_script` with the script in its `script` argument.
5. Use the script output in the final answer.
6. Keep scripts small and task-specific.

Rules:
1. Prefer standard library Python.
2. Print only the values you need.
3. Do not invent outputs without running the script.
4. If `execute_code` is not available, say exactly: `No Python execution tool is configured for this agent.`
5. Do not claim there is a generic execution-environment problem unless a tool call actually returned such an error.

Expected behavior:
- Explain the result briefly after using the script.
- Include the computed value or transformed output in the final answer.
