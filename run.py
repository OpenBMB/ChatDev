"""CLI entry point for executing ChatDev_new workflows."""
import argparse
import json
from pathlib import Path
from typing import List, Union

from runtime.bootstrap.schema import ensure_schema_registry_populated
from check.check import load_config
from entity.graph_config import GraphConfig
from entity.messages import Message
from utils.attachments import AttachmentStore
from utils.schema_exporter import build_schema_response, SchemaResolutionError
from utils.task_input import TaskInputBuilder
from workflow.graph_context import GraphContext
from workflow.graph import GraphExecutor

OUTPUT_ROOT = Path("WareHouse")


ensure_schema_registry_populated()

def build_task_input_payload(
    graph_context: GraphContext,
    prompt: str,
    attachment_paths: List[str]
) -> Union[str, List[Message]]:
    """Construct the initial task input, embedding attachments when available."""
    if not attachment_paths:
        return prompt

    code_workspace = graph_context.directory / "code_workspace"
    attachments_dir = code_workspace / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    store = AttachmentStore(attachments_dir)
    builder = TaskInputBuilder(store)
    return builder.build_from_file_paths(prompt, attachment_paths)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Run ChatDev_new workflow")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("yaml_instance/net_loop_test_included.yaml"),
        help="Path to the design_0.4.0 workflow file",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="test_project",
        help="Name of the project",
    )
    parser.add_argument(
        "--fn-module",
        dest="fn_module",
        default=None,
        help="Optional module providing edge helper functions referenced by the design",
    )
    parser.add_argument(
        "--inspect-schema",
        action="store_true",
        help="Output configuration schema (optionally scoped by breadcrumbs) and exit",
    )
    parser.add_argument(
        "--schema-breadcrumbs",
        type=str,
        default=None,
        help="JSON array describing schema breadcrumbs (e.g. '[{\"node\":\"DesignConfig\",\"field\":\"graph\"}]')",
    )
    parser.add_argument(
        "--attachment",
        action="append",
        default=[],
        help="Path to a file to attach to the initial user message (repeatable)",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_arguments()

    if args.inspect_schema:
        breadcrumbs = None
        if args.schema_breadcrumbs:
            try:
                breadcrumbs = json.loads(args.schema_breadcrumbs)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid --schema-breadcrumbs JSON: {exc}")
        try:
            schema = build_schema_response(breadcrumbs)
        except SchemaResolutionError as exc:
            raise SystemExit(f"Failed to resolve schema: {exc}")
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        return

    design = load_config(
        args.path,
        fn_module=args.fn_module,
    )

    task_prompt = input("Please enter the task prompt: ")

    # Create GraphConfig and GraphContext
    graph_config = GraphConfig.from_definition(
        design.graph,
        name=args.name,
        output_root=OUTPUT_ROOT,
        source_path=str(args.path),
        vars=design.vars,
    )
    graph_context = GraphContext(config=graph_config)

    task_input = build_task_input_payload(
        graph_context,
        task_prompt,
        args.attachment or [],
    )
    
    GraphExecutor.execute_graph(graph_context, task_input)

    print(graph_context.final_message())


if __name__ == "__main__":
    main()
