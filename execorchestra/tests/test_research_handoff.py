import json
import unittest
from pathlib import Path

import httpx

from scripts.prepare_research_profile import browser_input_contract, browser_output_schema
from scripts.research_browser import page_chunk
from sgar_mvp.src.controller_session import ControllerSessionInputSnapshotV1, ControllerSessionSpecV2
from sgar_mvp.src.controller_tool_runtime import normalize_provider_tool_calls
from sgar_mvp.src.controller_tooling import (
    ControllerToolingError, derive_controller_callable_tool_spec, project_provider_tool_schema,
    validate_callable_port_partition,
)
from sgar_mvp.src.executors import ControllerTurnExecutor
from sgar_mvp.src.model_transport import create_production_model_transport_bundle
from sgar_mvp.src.resource_runtime import ResourceDefinition


def sealed_reader(dynamic):
    root = Path(__file__).resolve().parents[1]
    template = root / "Pool/resources/tools/registry/python_script/searxng_search.json"
    raw = json.loads(template.read_text(encoding="utf8"))
    raw["io"] = {"input_contract": browser_input_contract(),
                 "output_contract": {"artifact_type": "json", "json_schema": browser_output_schema()}}
    definition = ResourceDefinition.from_manifest(raw)
    operation = definition.capability_card.capability_operations[0].capability_operation_id
    return derive_controller_callable_tool_spec(definition=definition, capability_operation_id=operation,
                                                capability_evidence_refs=[operation], fixed_input_bindings={},
                                                dynamic_input_names=dynamic)


class ContinuationTests(unittest.TestCase):
    def test_first_read_optional_followup_read_authorized(self):
        with self.assertRaisesRegex(ControllerToolingError, "continuation_port_unassigned"):
            sealed_reader(["url"])
        spec = sealed_reader(["url", "link_offset", "text_offset"])
        parameters = project_provider_tool_schema(spec)["function"]["parameters"]
        self.assertEqual(parameters["required"], ["url"])
        page = {"text": "x" * 6200 + "Copper", "links": [], "page_id": "fixture"}
        def invoke(args):
            call = {"id": "fixture-call", "type": "function", "function": {
                "name": spec.provider_tool_name, "arguments": json.dumps(args)}}
            (intent,) = normalize_provider_tool_calls(session_id="session", turn_id="turn",
                                                      raw_tool_calls=[call], callable_tools=[spec])
            return page_chunk(page, intent.normalized_dynamic_arguments.get("text_offset", 0))
        first = invoke({"url": "https://catalog.example/entry"})
        self.assertNotIn("Copper", first["text"])
        second = invoke({"url": "https://catalog.example/entry", "text_offset": first["next_text_offset"]})
        self.assertEqual(first["page_id"], second["page_id"])
        self.assertIn("Copper", second["text"])

    def test_opaque_cursor_fixed_binding_and_unrelated_optional_port(self):
        ports = [{"name": "collection", "kind": "string", "required": True},
                 {"name": "resume", "kind": "string", "required": False, "continuation_from": "more"},
                 {"name": "locale", "kind": "string", "required": False}]
        schema = {"json_schema": {"type": "object", "properties": {"more": {"type": ["null", "string"]}}}}
        def partition(fixed):
            return validate_callable_port_partition(operation_input_contract=ports, operation_output_contract=schema,
                                                     fixed_input_names=fixed, dynamic_input_names=["collection"])
        with self.assertRaisesRegex(ControllerToolingError, "continuation_port_unassigned"):
            partition([])
        fixed, dynamic = partition(["resume"])
        self.assertEqual([p["name"] for p in fixed], ["resume"])
        self.assertEqual([p["name"] for p in dynamic], ["collection"])
        schema["json_schema"]["properties"]["more"] = {"type": "boolean"}
        with self.assertRaisesRegex(ControllerToolingError, "continuation_source_invalid"):
            partition(["resume"])
        del ports[1]["continuation_from"]
        self.assertEqual(partition([])[0], ())


class WireTests(unittest.IsolatedAsyncioTestCase):
    async def test_condition_for_external_lookup_reaches_provider(self):
        tool = sealed_reader(["url", "text_offset", "link_offset"])
        spec = ControllerSessionSpecV2(
            subtask_id="example", subtask_revision=0, controller_step_id="inspect",
            controller_resource_id="model.fixture", controller_resource_type="Model",
            backing_model_resource_id="model.fixture", controller_session_policy_sha256="0"*64,
            expected_output_contract={"artifact_type": "text"}, task_instruction="Inspect catalog.",
            callable_tools=(tool,), callable_tool_scope=(tool.callable_id,))
        snapshot = ControllerSessionInputSnapshotV1(session_id="fixture", spec_sha256=spec.spec_sha256,
                                                   resolved_input_descriptors=())
        received = []
        def respond(request):
            received.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "fixture", "created": 1, "model": "fixture",
                "object": "chat.completion", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Copper"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}})
        context = {"external_discovery_mode": "if_needed", "source_discovery_instruction": "Use supplied locators first.",
                   "external_acquisition_mode": "if_needed", "conditional_evidence_instruction": "Read when evidence is missing."}
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ac:
            with httpx.Client(transport=httpx.MockTransport(respond)) as sc:
                transport = create_production_model_transport_bundle(api_key="offline", base_url="https://fixture.invalid/v1",
                                                                      sync_http_client=sc, async_http_client=ac)
                await ControllerTurnExecutor(transport=transport.async_port, max_retries=1).execute_turn(
                    spec=spec, snapshot=snapshot, turn_id="one", turn_index=1,
                    provider_tools=[project_provider_tool_schema(tool)],
                    controller_context={"provider_model_id": "fixture", **context})
        payload = json.loads(received[0]["messages"][1]["content"])
        self.assertEqual({k: payload[k] for k in context}, context)
