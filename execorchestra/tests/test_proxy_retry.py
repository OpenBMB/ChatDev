"""Exercise the cluster cooldown with the normal SDK and Profiler retry owner."""
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import APIConnectionError, OpenAI

from sgar_mvp.src import proxy_retry
from sgar_mvp.src.direct_network import direct_sync_http_client
from sgar_mvp.src.model_request_budget import ModelRequestBudget, model_request_budget
from sgar_mvp.src.model_transport import ProviderEndpointIdentity, SyncModelTransportPort


class ProxyRetryTests(unittest.TestCase):
    def test_profiler_recovers_after_proxy_starts_listening(self):
        template = Path(__file__).resolve().parents[1] / "configs/retrieval_policy.example.json"
        with patch.dict(os.environ, {"SGAR_RETRIEVAL_POLICY_PATH": str(template),
                                     "SGAR_SEALED_LOCAL_VALIDATION": "1"}):
            import retrieve

        posts = []
        profile = {"think": "The question needs published hours.",
                   "capability_text": "Look up library opening hours.",
                   "constraint_text": "Use the official source."}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                posts.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                response = json.dumps({"choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps(profile)}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), Handler, bind_and_activate=False) as proxy:
            proxy.server_bind()
            proxy.timeout = 3
            worker = threading.Thread(target=proxy.handle_request, daemon=True)
            def recover(delay):
                self.assertTrue(5 <= delay <= 6)
                proxy.server_activate()
                worker.start()

            # No external name resolution: this HTTP proxy itself serves the SDK response.
            base = "http://unreachable.invalid/v1"
            endpoint = ProviderEndpointIdentity.create(provider="test", base_url=base,
                credential_environment_variable="DUMMY_KEY", timeout_seconds=4)
            with patch.dict(os.environ, {"SGAR_MODEL_PROXY": f"http://127.0.0.1:{proxy.server_port}"}):
                with OpenAI(api_key="test", base_url=base, max_retries=0, timeout=4,
                            http_client=direct_sync_http_client()) as sdk:
                    port = SyncModelTransportPort.from_sdk_client(client=sdk, endpoint_identity=endpoint)
                    def request():
                        return retrieve._generate_hyde_result("Find the library's opening hours.",
                            transport=port, model_attempt_limit=1, allow_direct_fallback=False)

                    with patch.dict(os.environ, {"SGAR_PROXY_CONNECT_BACKOFF":"0"}):
                        with self.assertRaises(retrieve.HyDEGenerationError) as before:
                            request()
                        self.assertEqual(before.exception.transport_attempts,
                                         retrieve.RETRIEVAL_POLICY.hyde.max_transport_attempts_per_model_attempt)
                    with patch.dict(os.environ, {"SGAR_PROXY_CONNECT_BACKOFF":"1"}), patch.object(proxy_retry, "time") as clock:
                        clock.sleep.side_effect = recover
                        result = request()
                        clock.sleep.assert_called_once()
            worker.join(3)
        self.assertEqual(len(posts), 1)
        self.assertEqual(result["capability_text"], profile["capability_text"])
        self.assertEqual(result["metadata"]["transport_attempt_count"], 2)
        self.assertEqual(len(set(result["metadata"]["transport_request_hashes"])), 1)

    def test_no_wait_on_response_loss_or_unrelated_connection_errors(self):
        req = httpx.Request("POST", "https://invalid.test")
        with patch.dict(os.environ, {"SGAR_PROXY_CONNECT_BACKOFF":"1", "SGAR_MODEL_PROXY":"http://127.0.0.1:9999"}), patch.object(proxy_retry, "time") as clock:
            for cause in (httpx.RemoteProtocolError("reply lost"), httpx.ReadTimeout("read"),
                          httpx.ConnectError("TLS error"), httpx.ProxyError("tunnel rejected")):
                error = APIConnectionError(request=req)
                error.__cause__ = cause
                self.assertTrue(proxy_retry.wait_for_proxy_retry(error, 1))
            clock.sleep.assert_not_called()

    def test_insufficient_time_preserves_reserve(self):
        error = httpx.ConnectError("connection failed")
        error.__cause__ = ConnectionRefusedError()
        budget = ModelRequestBudget(deadline_monotonic=time.monotonic()+20,
                                    minimum_attempt_seconds=15, downstream_reserve_seconds=4)
        with patch.dict(os.environ, {"SGAR_PROXY_CONNECT_BACKOFF":"1", "SGAR_MODEL_PROXY":"http://127.0.0.1:9999"}), model_request_budget(budget), patch.object(proxy_retry, "time") as clock:
            self.assertFalse(proxy_retry.wait_for_proxy_retry(error, 2))
            clock.sleep.assert_not_called()
