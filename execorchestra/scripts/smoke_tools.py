"""Run fresh tool checks using the formal smoke runner and synthetic inputs."""
import json
import os
import sys
from pathlib import Path
from sgar_mvp.scripts import run_tool_smoke_tests as runner

ROOT = Path(__file__).resolve().parents[1]
original_args = runner.smoke_args
original_run = runner.run

def smoke_args(manifest, workspace):
    p = lambda name: runner.container_path(workspace / name)
    extra = {
        "tool.check_jsonschema_validate.v1": [p("schema.json"), p("sample.json")],
        "tool.duckdb_query.v1": ["SELECT 17 + 25 AS answer"],
        "tool.ripgrep_search.v1": ["RC1", p("sample.md")],
        "tool.trafilatura_extract.v1": [p("sample.html")],
        "tool.httpx_download.v1": ["https://example.com", p("download.html")],
        "tool.searxng_search.v1": ["Python documentation"],
        "tool.browser_read_page.v1": ["https://example.com"],
        "tool.zotero_translation.v1": ["10.1038/nature14539"],
        "tool.hypothesis_annotation.v1": ["https://example.com"],
    }
    rid = manifest["resource_id"]
    return extra[rid] if rid in extra else original_args(manifest, workspace)

def run(command, **kwargs):
    # Pass variables by name, keeping credentials out of command arguments.
    if command[:2] == ["docker", "run"]:
        names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "EXA_API_KEY",
                 "SEARXNG_BASE_URL", "ZOTERO_TRANSLATION_SERVER_URL",
                 "SGAR_BROWSER_BASE_URL", "SGAR_BROWSER_TOKEN",
                 "HYPOTHESIS_API_URL", "HYPOTHESIS_API_TOKEN")
        env_args = [arg for name in names if os.environ.get(name) for arg in ("-e", name)]
        command = command[:2] + env_args + command[2:]
    return original_run(command, **kwargs)

def main():
    candidates = json.loads((ROOT / "Pool/resources/json/effective_tools.json").read_text())
    # Task-container wrappers are checked in their benchmark task images by the
    # existing adapter. Running them in the shared RC1 image is not valid.
    selected = [x for x in candidates if x.get("runtime_requirements", {}).get("runtime_profile") != "task-container"]
    runner.smoke_args = smoke_args
    runner.run = run
    sys.argv = [sys.argv[0], "--tools", str(ROOT / "Pool/resources/json/effective_tools.json")]
    for item in selected:
        sys.argv += ["--tool-id", item["resource_id"]]
    return runner.main()

if __name__ == "__main__":
    raise SystemExit(main())
