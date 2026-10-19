import importlib.util
import sys
import types
from pathlib import Path


def _load_openai_provider() -> type:
    """Load OpenAIProvider in an isolated mock namespace without heavy runtime deps."""
    runtime = types.ModuleType("runtime")
    runtime.__path__ = []
    runtime_node = types.ModuleType("runtime.node")
    runtime_node.__path__ = []
    runtime_agent = types.ModuleType("runtime.node.agent")
    runtime_providers = types.ModuleType("runtime.node.agent.providers")
    runtime_providers.__path__ = []
    response_module = types.ModuleType("runtime.node.agent.providers.response")

    model_provider = type("ModelProvider", (), {})
    model_response = type("ModelResponse", (), {})
    runtime_agent.ModelProvider = model_provider
    runtime_agent.ModelResponse = model_response
    response_module.ModelResponse = model_response

    module_names = {
        "runtime": runtime,
        "runtime.node": runtime_node,
        "runtime.node.agent": runtime_agent,
        "runtime.node.agent.providers": runtime_providers,
        "runtime.node.agent.providers.response": response_module,
    }
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    sys.modules.update(module_names)
    try:
        module_name = "chatdev_test_openai_provider_impl"
        module_path = Path(__file__).parents[1] / "runtime/node/agent/providers/openai_provider.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module.OpenAIProvider
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


OpenAIProvider = _load_openai_provider()


def _provider() -> OpenAIProvider:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model_name = "test-model"
    provider.params = {}
    return provider


def test_chat_payload_sets_default_timeout() -> None:
    payload = _provider()._build_chat_payload(
        conversation=[],
        tool_specs=None,
        raw_params={},
    )
    assert payload["timeout"] == 300


def test_chat_payload_respects_custom_timeout() -> None:
    raw_params = {"timeout": 45}
    payload = _provider()._build_chat_payload(
        conversation=[],
        tool_specs=None,
        raw_params=raw_params,
    )
    assert payload["timeout"] == 45


def test_responses_payload_sets_default_timeout() -> None:
    payload = _provider()._build_request_payload(
        timeline=[],
        tool_specs=None,
        raw_params={},
    )
    assert payload["timeout"] == 300


def test_responses_payload_respects_custom_timeout() -> None:
    raw_params = {"timeout": 60}
    payload = _provider()._build_request_payload(
        timeline=[],
        tool_specs=None,
        raw_params=raw_params,
    )
    assert payload["timeout"] == 60
