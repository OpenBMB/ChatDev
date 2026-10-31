"""Embedding chunking respects configured limits without dropping input text."""

import json

import httpx
import openai
import pytest

from runtime.node.agent.memory.embedding import OpenAIEmbedding
from entity.configs import EmbeddingConfig


@pytest.fixture
def embedding_factory():
    clients = []

    def create(max_length=64, strategy="average"):
        requests = []

        def respond(request):
            payload = json.loads(request.content)
            requests.append(payload)
            if len(payload["input"]) > max_length:
                return httpx.Response(
                    400, json={"error": {"message": "input exceeds configured limit"}}
                )
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "test-embedding",
                    "data": [
                        {
                            "object": "embedding",
                            "index": 0,
                            "embedding": [0.125, 0.25, 0.5],
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )

        config = EmbeddingConfig.from_dict(
            {
                "provider": "openai",
                "model": "test-embedding",
                "api_key": "test-key",
                "params": {
                    "use_chunking": True,
                    "max_length": max_length,
                    "chunk_strategy": strategy,
                },
            },
            path="embedding",
        )
        embedding = OpenAIEmbedding(config)
        embedding.client.close()
        embedding.client = openai.OpenAI(
            api_key="test-key",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        clients.append(embedding.client)
        return embedding, requests

    yield create
    for client in clients:
        client.close()


@pytest.mark.parametrize("strategy", ["average", "weighted", "first"])
@pytest.mark.parametrize(
    ("max_length", "text", "chunked"),
    [
        (64, "word " * 60, True),
        (64, "中文知识" * 80, True),
        (1, "abcd", True),
        (64, "short text", False),
        (64, "x" * 64, False),
    ],
)
def test_public_embedding_requests_stay_within_the_configured_limit(
    embedding_factory, strategy, max_length, text, chunked
):
    embedding, requests = embedding_factory(max_length, strategy)

    result = embedding.get_embedding(text)

    assert result == pytest.approx([0.125, 0.25, 0.5])
    assert requests
    assert all(0 < len(payload["input"]) <= max_length for payload in requests)
    assert (len(requests) > 1) is chunked
    assert "".join(payload["input"] for payload in requests) == text.strip()


@pytest.mark.parametrize(
    ("text", "limit"),
    [
        ("abcdefghijk", 4),
        ("甲乙。丙丁！戊己？庚辛；尾", 5),
        ("ab\ncd\n\nefghij", 3),
        ("abcde", 5),
        ("", 5),
    ],
)
def test_chunks_preserve_every_input_character(embedding_factory, text, limit):
    embedding, _ = embedding_factory()

    chunks = embedding._chunk_text(text, limit)

    assert "".join(chunks) == text
    assert all(len(chunk) <= limit for chunk in chunks)


@pytest.mark.parametrize("limit", [0, -1])
def test_chunk_size_must_be_positive(embedding_factory, limit):
    embedding, _ = embedding_factory()

    with pytest.raises(ValueError, match="max_length"):
        embedding._chunk_text("abc", limit)
