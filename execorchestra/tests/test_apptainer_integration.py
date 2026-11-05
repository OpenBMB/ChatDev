"""Opt-in real-container checks. Run only in a scheduled compute allocation."""
from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
import unittest

from sgar_mvp.src.apptainer_runtime import ApptainerExecutionSubstrate


@unittest.skipUnless(os.environ.get("SGAR_TEST_APPTAINER_IMAGE"), "real image not configured")
class ApptainerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = ApptainerExecutionSubstrate(
            image=Path(os.environ["SGAR_TEST_APPTAINER_IMAGE"]),
            image_sha256=os.environ["SGAR_TEST_APPTAINER_SHA256"],
            apptainer=Path(os.environ["SGAR_TEST_APPTAINER_BIN"]),
            tools_prefix=Path(os.environ["SGAR_TEST_CONTAINER_TOOLS"]),
            state_dir=Path(os.environ["SGAR_TEST_APPTAINER_STATE"]),
            run_id="integration-" + os.environ["SLURM_JOB_ID"], trial_id="integration",
            network_allowed=True,
        )
        cls.runtime.require_pipeline_ready()

    def test_real_file_io_and_byte_identity(self):
        runtime = self.runtime
        asyncio.run(runtime.write_text("/app/sub/utf8.txt", "确定性工具\n"))
        self.assertEqual(asyncio.run(runtime.read_text("/app/sub/utf8.txt")), "确定性工具\n")
        self.assertEqual(asyncio.run(runtime.read_bytes("/app/sub/utf8.txt")), "确定性工具\n".encode())
        self.assertFalse(asyncio.run(runtime.exists("/app/missing")))

    def test_host_tree_and_ambient_secrets_hidden(self):
        from unittest.mock import patch

        private_dir = self.runtime.private_dir.resolve()
        self.assertTrue(private_dir.is_dir())
        with patch.dict(os.environ, {"LLM_API_KEY": "integration-fake-secret",
                                     "APPTAINERENV_INJECTED_FROM_HOST": "integration-fake-secret"}):
            result = self.runtime.call("exec_argv", argv=["python3", "-c",
                "import os,pathlib,sys; "
                "assert not pathlib.Path(sys.argv[1]).exists(); "
                "assert 'LLM_API_KEY' not in os.environ; "
                "assert 'INJECTED_FROM_HOST' not in os.environ; print('isolated')",
                str(private_dir)])
            self.assertTrue(result["ok"], result)

    def test_read_only_image(self):
        result = self.runtime.call("exec_argv", argv=["python3", "-c",
            "from pathlib import Path; "
            "p=Path('/usr/local/sgar-should-not-write'); "
            "\ntry: p.write_text('bad')\nexcept OSError: print('read-only')\nelse: raise AssertionError('writable image')"])
        self.assertTrue(result["ok"], result)

    def test_runtime_home_and_cache_are_task_owned(self):
        result = self.runtime.call("exec_argv", argv=["python3", "-c",
            "import os,pathlib; assert os.environ['HOME']=='/tmp/home'; "
            "p=pathlib.Path(os.environ['XDG_CACHE_HOME'])/'cache-probe'; "
            "p.parent.mkdir(parents=True,exist_ok=True); p.write_text('task cache'); "
            "print(p.read_text())"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stdout"].strip(), "task cache")

    def test_symlink_cannot_read_host_private_file(self):
        secret = self.runtime.private_dir / "private-marker"
        secret.write_text("not task data")
        result = self.runtime.call("exec_argv", argv=["python3", "-c",
            "import pathlib,sys; pathlib.Path('/app/host-link').symlink_to(sys.argv[1])", str(secret)])
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.runtime.call("read_text", path="/app/host-link")["ok"])

    def test_network_scope(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b"allocated-node-probe")
            def log_message(self, *args):
                pass
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            script = "import urllib.request,sys; print(urllib.request.urlopen(sys.argv[1],timeout=2).read().decode())"
            argv = ["python3", "-c", script, f"http://127.0.0.1:{server.server_port}"]
            try:
                offline = self.runtime.call("exec_argv", argv=argv, timeout_sec=15)
                online = self.runtime.call("exec_argv", argv=argv, network_required=True, timeout_sec=15)
                self.assertFalse(offline["ok"])
                self.assertTrue(online["ok"], online)
                self.assertEqual(online["stdout"].strip(), "allocated-node-probe")
            finally:
                server.shutdown(); worker.join(timeout=3)

    def test_timeout_stops_container_children(self):
        script = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c',"
            + repr("import time,pathlib; time.sleep(3); pathlib.Path('/app/late-child').touch()")
            + "]); time.sleep(60)"
        )
        result = self.runtime.call("exec_argv", argv=["python3", "-c", script], timeout_sec=2)
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("error_type"), "RESOURCE_EXECUTION_TIMEOUT", result)
        time.sleep(3.1)
        self.assertFalse(asyncio.run(self.runtime.exists("/app/late-child")))


if __name__ == "__main__":
    unittest.main()
