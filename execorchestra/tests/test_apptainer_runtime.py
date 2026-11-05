"""Boundary regressions; no GPU, providers or real container launches."""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from sgar_mvp.src.apptainer_runtime import ApptainerExecutionSubstrate, ApptainerRuntimeError


class ApptainerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "image.sif"
        self.image.write_bytes(b"test image identity")
        self.exe = self.root / "apptainer"
        self.exe.touch()
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.environment = patch.dict(os.environ, {"SLURM_JOB_ID": "test-allocation"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.platform = patch("sgar_mvp.src.apptainer_runtime.sys.platform", "linux")
        self.platform.start()
        self.addCleanup(self.platform.stop)

    def make(self, **extra):
        return ApptainerExecutionSubstrate(image=self.image,
            image_sha256=hashlib.sha256(self.image.read_bytes()).hexdigest(),
            state_dir=self.root / "new-state", run_id="test", trial_id="test",
            apptainer=self.exe, tools_prefix=self.tools, **extra)

    def test_no_ambient_secret_or_mount_inheritance(self):
        with patch.dict(os.environ, {"APPTAINER_BIND": "/private:/private",
                                    "APPTAINERENV_LEAK": "secret", "LLM_API_KEY": "secret"}):
            runtime = self.make()
            command, env = runtime._command(["python3", "-V"], network=False, cwd="/app", extra_env={})
        self.assertNotIn("APPTAINER_BIND", env)
        self.assertNotIn("APPTAINERENV_LEAK", env)
        self.assertNotIn("LLM_API_KEY", env)
        self.assertIn("--no-eval", command)
        self.assertIn("home,cwd,hostfs,bind-paths", command)
        self.assertIn("none", command)
        self.assertIn(str(self.tools / "sbin"), env["PATH"])
        self.assertEqual(command.count("--bind"), 2)

    def test_network_is_opt_in_per_call(self):
        runtime = self.make(network_allowed=True, network_env={"https_proxy": "private-proxy"})
        offline, env = runtime._command(["true"], network=False, cwd="/app", extra_env={})
        online, online_env = runtime._command(["true"], network=True, cwd="/app", extra_env={})
        self.assertIn("--net", offline)
        self.assertNotIn("APPTAINERENV_https_proxy", env)
        self.assertNotIn("--net", online)
        self.assertEqual(online_env["APPTAINERENV_https_proxy"], "private-proxy")

    def test_no_runtime_or_proxy_override_from_tool(self):
        runtime = self.make()
        for key in ("APPTAINER_BIND", "SINGULARITYENV_X", "LD_PRELOAD", "PATH", "https_proxy"):
            with self.subTest(key=key), self.assertRaises(ApptainerRuntimeError):
                runtime._command(["true"], network=False, cwd="/app", extra_env={key: "bad"})
        with self.assertRaises(ApptainerRuntimeError):
            runtime._command(["true"], network=True, cwd="/app", extra_env={})

    def test_state_is_never_reused_and_image_mutation_is_rejected(self):
        runtime = self.make()
        with self.assertRaises(FileExistsError):
            self.make()
        self.image.write_bytes(b"changed")
        with self.assertRaises(ApptainerRuntimeError):
            runtime._command(["true"], network=False, cwd="/app", extra_env={})

    def test_file_rpc_does_not_read_or_write_task_paths_on_host(self):
        runtime = self.make()
        target = str(self.root / "must-not-be-created")
        with patch.object(runtime, "_run", return_value={"ok": True, "stdout": '{"ok": true}'}) as run:
            runtime.call("write_text", path=target, text="private payload")
        self.assertFalse(Path(target).exists())
        self.assertIn(b"private payload", run.call_args.kwargs["payload"])
        self.assertNotIn("private payload", repr(runtime.records))

    def test_file_identity_checks_are_reused(self):
        runtime = self.make()
        with patch.object(runtime, "call", return_value={"ok": True, "data_base64": "eA==",
                "byte_size": 1, "content_sha256": "wrong"}):
            with self.assertRaises(RuntimeError):
                asyncio.run(runtime.read_bytes("/app/file"))

    @unittest.skipUnless(os.name == "posix", "POSIX process supervision")
    def test_timeout_kills_descendants_before_they_write(self):
        runtime = self.make()
        marker = self.root / "escaped-child"
        # A stand-in process verifies supervision independently of Apptainer.
        script = ("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
                  + repr("import time,pathlib; time.sleep(2); pathlib.Path(" + repr(str(marker)) + ").touch()")
                  + "]); time.sleep(10)")
        with patch.object(runtime, "_command", return_value=([sys.executable, "-c", script], dict(os.environ))):
            result = runtime._run(["unused"], timeout_sec=0.15)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "RESOURCE_EXECUTION_TIMEOUT")
        import time
        time.sleep(2.1)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX process supervision")
    def test_output_is_bounded(self):
        runtime = self.make(max_output_bytes=1024)
        with patch.object(runtime, "_command", return_value=(
                [sys.executable, "-c", "import sys; sys.stdout.write('x'*1000000)"], dict(os.environ))):
            result = runtime._run(["unused"], timeout_sec=5)
        self.assertFalse(result["ok"])
        self.assertTrue(result["stdout_truncated"])
        self.assertEqual(len(result["stdout"]), 1024)


if __name__ == "__main__":
    unittest.main()
