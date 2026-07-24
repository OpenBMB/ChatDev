"""Unit tests for OpenAIProvider streaming aggregation (#653)."""

from types import SimpleNamespace

from runtime.node.agent.providers.openai_provider import OpenAIProvider


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

        class _Completions:
            def __init__(self, outer):
                self._outer = outer

            def create(self, **kwargs):
                self._outer.last_kwargs = kwargs
                return _FakeStream(self._outer._chunks)

        class _Chat:
            def __init__(self, outer):
                self.completions = _Completions(outer)

        self.chat = _Chat(self)


def _delta_chunk(content=None, tool_calls=None, usage=None, id_="chatcmpl-1", model="gpt-test"):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, index=0)
    return SimpleNamespace(id=id_, model=model, choices=[choice], usage=usage)


def test_chat_completion_forces_stream_and_aggregates_content():
    chunks = [
        _delta_chunk(content="Hello"),
        _delta_chunk(content=" world", usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)),
    ]
    client = _FakeClient(chunks)
    provider = OpenAIProvider(model_name="gpt-test", params={})

    response = provider._chat_completion(client, {"model": "gpt-test", "messages": []})

    assert client.last_kwargs["stream"] is True
    assert client.last_kwargs["stream_options"] == {"include_usage": True}
    assert response.choices[0].message.content == "Hello world"
    assert response.usage.total_tokens == 3


def test_chat_completion_aggregates_tool_call_deltas():
    tc0_a = SimpleNamespace(
        index=0,
        id="call_1",
        type="function",
        function=SimpleNamespace(name="search", arguments='{"q":'),
    )
    tc0_b = SimpleNamespace(
        index=0,
        id=None,
        type=None,
        function=SimpleNamespace(name=None, arguments='"ai"}'),
    )
    chunks = [
        _delta_chunk(tool_calls=[tc0_a]),
        _delta_chunk(tool_calls=[tc0_b]),
    ]
    client = _FakeClient(chunks)
    provider = OpenAIProvider(model_name="gpt-test", params={})

    response = provider._chat_completion(client, {"model": "gpt-test", "messages": []})
    tc = response.choices[0].message.tool_calls[0]
    assert tc.id == "call_1"
    assert tc.function.name == "search"
    assert tc.function.arguments == '{"q":"ai"}'
