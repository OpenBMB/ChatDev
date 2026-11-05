"""Service validation paths only; no model loading, GPU work or server startup."""
import asyncio
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "separate embedding service dependencies not installed")
class EmbeddingServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts import embedding_server
        cls.service = embedding_server

    def test_pinned_identity_matches_framework_template(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "configs/embedding_release.example.json").read_text())['runtime']
        self.assertEqual(self.service.REVISION, config['revision'])
        self.assertEqual(self.service.DIMENSION, config['output_dimension'])
        self.assertEqual(self.service.MAX_TOKENS, config['max_tokens'])
        self.assertEqual(self.service.MODEL_ID, config['api_model_id'])

    def test_no_model_is_loaded_on_import(self):
        self.assertEqual(self.service.state, {})
        with self.assertRaises(self.service.HTTPException) as caught:
            self.service.health()
        self.assertEqual(caught.exception.status_code, 503)

    def test_request_requires_private_key(self):
        body = self.service.EmbeddingRequest(model=self.service.MODEL_ID, input="hello")
        with patch.dict('os.environ', {"SGAR_EMBEDDING_API_KEY": "service-test-only"}):
            with self.assertRaises(self.service.HTTPException) as caught:
                self.service.embeddings(body, authorization="Bearer wrong-key")
        self.assertEqual(caught.exception.status_code, 401)

    def test_dimensions_and_encoding_are_checked_before_inference(self):
        for values in [{"dimensions": 1024}, {"encoding_format": "base64"}, {"model": "other"}]:
            body = self.service.EmbeddingRequest(**{"model": self.service.MODEL_ID, "input": "hello", **values})
            with patch.dict('os.environ', {"SGAR_EMBEDDING_API_KEY": "service-test-only"}):
                with self.assertRaises(self.service.HTTPException) as caught:
                    self.service.embeddings(body, authorization="Bearer service-test-only")
            self.assertEqual(caught.exception.status_code, 400)

    def test_request_size_is_bounded_before_inference(self):
        for inputs in [[], ["hello"] * 65]:
            body = self.service.EmbeddingRequest(model=self.service.MODEL_ID, input=inputs)
            with patch.dict('os.environ', {"SGAR_EMBEDDING_API_KEY": "service-test-only"}):
                with self.assertRaises(self.service.HTTPException) as caught:
                    self.service.embeddings(body, authorization="Bearer service-test-only")
            self.assertEqual(caught.exception.status_code, 400)

    def test_startup_requires_explicit_allocation(self):
        async def attempt():
            async with self.service.lifespan(None):
                self.fail("model must not start without an allocation")
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Slurm GPU allocation"):
                asyncio.run(attempt())
