"""Readiness must not accept another backend's evidence or stale image IDs."""
import json
from pathlib import Path
import unittest

from sgar_mvp.src.resource_readiness import RC1ReadinessBuilder


ROOT = Path(__file__).resolve().parents[1]


class RuntimeReadinessTests(unittest.TestCase):
    def setUp(self):
        catalog = json.loads((ROOT / "Pool/resources/json/combine.json").read_text(encoding="utf-8"))
        self.tool = next(x for x in catalog if x["resource_id"] == "tool.xlsx2csv.v1")
        self.hash = "a" * 64
        self.lock = {"runtime_backend": "apptainer", "runtime_image_sha256": self.hash}
        self.row = {"resource_id": self.tool["resource_id"], "status": "ready", "smoke_passed": True,
                    "source_hash": self.tool["provenance"]["source_hash"],
                    "runtime_backend": "apptainer", "runtime_image_sha256": self.hash}
        self.smoke = {"runtime_backend": "apptainer", "runtime_image_sha256": self.hash,
                      "tools": [self.row]}

    def entry(self):
        return RC1ReadinessBuilder(ROOT, [self.tool], runtime_lock=self.lock,
                                   tool_smoke=self.smoke)._tool(self.tool)

    def test_exact_image_and_source_evidence_is_ready(self):
        self.assertEqual(self.entry().readiness_status, "ready")

    def test_source_mutation_is_not_hidden_by_correct_runtime(self):
        self.row["source_hash"] = "sha256:" + "b" * 64
        self.assertIn("smoke_source_hash_mismatch", self.entry().reasons)

    def test_wrong_image_in_report_or_row_is_blocked(self):
        self.smoke["runtime_image_sha256"] = "b" * 64
        self.assertIn("smoke_runtime_digest_mismatch", self.entry().reasons)
        self.smoke["runtime_image_sha256"] = self.hash
        self.row["runtime_image_sha256"] = "b" * 64
        self.assertIn("smoke_resource_runtime_identity_mismatch", self.entry().reasons)

    def test_docker_evidence_cannot_admit_apptainer(self):
        self.smoke["runtime_backend"] = "docker"
        self.assertIn("smoke_runtime_backend_mismatch", self.entry().reasons)

    def test_default_docker_path_remains_supported(self):
        self.lock = {"image_id": "sha256:" + self.hash}
        self.smoke = {"docker_image_id": self.lock["image_id"], "tools": [self.row]}
        self.assertEqual(self.entry().readiness_status, "ready")

    def test_unknown_backend_fails_closed(self):
        self.lock["runtime_backend"] = "unverified"
        self.assertIn("runtime_backend_unsupported", self.entry().reasons)


if __name__ == "__main__":
    unittest.main()
