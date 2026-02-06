#!/usr/bin/env python3
"""Run ChatDev with Claude Code provider."""

import sys
sys.path.insert(0, '.')

from runtime import run_workflow

result = run_workflow(
    "yaml_instance/ChatDev_v1_claude.yaml",
    task_prompt="Build a Python calculator that can add, subtract, multiply and divide two numbers. Single file, command-line interface.",
    session_name="calculator_test",
    log_level="DEBUG",
)

print("\n" + "=" * 60)
print("WORKFLOW COMPLETED")
print("=" * 60)
if result.final_message:
    print(f"Final message: {result.final_message.text_content()[:500]}")
print(f"Session: {result.meta_info.session_name}")
print(f"Output dir: {result.meta_info.output_dir}")
if result.meta_info.token_usage:
    print(f"Token usage: {result.meta_info.token_usage}")
