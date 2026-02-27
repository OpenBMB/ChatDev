"""Register built-in agent providers."""

from runtime.node.agent.providers.base import ProviderRegistry

from runtime.node.agent.providers.openai_provider import OpenAIProvider

ProviderRegistry.register(
    "openai",
    OpenAIProvider,
    label="OpenAI",
    summary="OpenAI models via the official OpenAI SDK (responses API)",
)

try:
    from runtime.node.agent.providers.doubao_provider import DoubaoProvider
except ImportError:
    DoubaoProvider = None

if DoubaoProvider is not None:
    ProviderRegistry.register(
        "doubao",
        DoubaoProvider,
        label="Doubao",
        summary="ByteDance Doubao models via OpenAI-compatible API",
    )
else:
    print("Doubao provider not registered.")

try:
    from runtime.node.agent.providers.gemini_provider import GeminiProvider
except ImportError:
    GeminiProvider = None

if GeminiProvider is not None:
    ProviderRegistry.register(
        "gemini",
        GeminiProvider,
        label="Google Gemini",
        summary="Google Gemini models via google-genai",
    )
else:
    print("Gemini provider not registered: google-genai library not found.")
