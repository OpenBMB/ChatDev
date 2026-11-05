import json
import socket
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.research_browser import public_host
from scripts.prepare_research_profile import declare_search_read
from sgar_mvp.src.capability_cards import build_capability_card
from sgar_mvp.src.controller_session import _validate_finalization_evidence_audit


class ResearchRecoveryTests(unittest.TestCase):
    def test_only_query_adapter_acquires_read_only_contract(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "Pool/resources/tools/registry/python_script/searxng_search.json").read_text())
        declare_search_read(manifest)
        operations = build_capability_card(manifest).capability_operations
        self.assertTrue(operations)
        self.assertTrue(all(op.side_effects == "none" and not op.effect_targets for op in operations))
        manifest["io"]["input_contract"].append({"name": "base_url"})
        with self.assertRaises(ValueError):
            declare_search_read(manifest)

    def test_incomplete_receipt_reports_empty_and_omitted_criteria(self):
        observation = SimpleNamespace(status="success", observation_sha256="a" * 64)
        receipt = {"ready": False, "latest_observation_id": "obs_1",
                   "latest_observation_supports_completion": False, "final_output": "",
                   "criterion_evidence": [{"criterion_index": 1, "observation_ids": ["obs_1"]},
                                          {"criterion_index": 0, "observation_ids": []}]}
        diagnostics = {}
        result = _validate_finalization_evidence_audit(
            json.dumps(receipt), acceptance_criteria=["one", "two", "three"],
            tool_results=[SimpleNamespace(observation=observation)], diagnostics=diagnostics)
        self.assertEqual(result, (False, "", "$:finalization_evidence_unsatisfied"))
        self.assertEqual(diagnostics["missing_criterion_indices"], [0, 2])

    @patch("scripts.research_browser.time.sleep")
    def test_only_temporary_dns_failure_retries_and_addresses_are_rechecked(self, _sleep):
        temporary = socket.gaierror(socket.EAI_AGAIN, "temporary lookup failure")
        for address, expected in [("93.184.216.34", True), ("127.0.0.1", False)]:
            with patch("socket.getaddrinfo", side_effect=[temporary, [(0, 0, 0, "", (address, 0))]]) as lookup:
                self.assertEqual(public_host("source.example"), expected)
                self.assertEqual(lookup.call_count, 2)
        for errors, count in [([socket.gaierror(socket.EAI_NONAME, "unknown host")], 1),
                              ([temporary, temporary], 2)]:
            with patch("socket.getaddrinfo", side_effect=errors) as lookup:
                self.assertFalse(public_host("source.example"))
                self.assertEqual(lookup.call_count, count)
