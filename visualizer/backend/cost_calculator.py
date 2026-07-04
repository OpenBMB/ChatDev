# ══════════════════════════════════════════════════════════════════
#   cost_calculator.py — Real Token-Based Cost Calculation Engine
#
#   Replaces the hardcoded `step_cost = 0.002` with actual
#   per-model pricing based on prompt/completion token counts.
#
#   Features:
#     - Model-specific pricing table (updated 2024/2025 rates)
#     - Automatic token estimation when exact count unavailable
#     - Currency formatting and cost aggregation
# ══════════════════════════════════════════════════════════════════

import logging
import math
from datetime import datetime

logger = logging.getLogger("chatdev.cost_calculator")


# ══════════════════════════════════════════════════════════════
#   Model Pricing Table (USD per 1M tokens)
# ══════════════════════════════════════════════════════════════

MODEL_PRICING = {
    # ── OpenAI ──
    "gpt-4o":               {"input": 2.50,   "output": 10.00},
    "gpt-4o-mini":          {"input": 0.15,   "output": 0.60},
    "gpt-4-turbo":          {"input": 10.00,  "output": 30.00},
    "gpt-4":                {"input": 30.00,  "output": 60.00},
    "gpt-3.5-turbo":        {"input": 0.50,   "output": 1.50},
    "o1":                   {"input": 15.00,  "output": 60.00},
    "o1-mini":              {"input": 3.00,   "output": 12.00},
    "o3-mini":              {"input": 1.10,   "output": 4.40},

    # ── Anthropic ──
    "claude-opus-4-5":              {"input": 15.00,  "output": 75.00},
    "claude-sonnet-4-5":            {"input": 3.00,   "output": 15.00},
    "claude-3-5-sonnet-20241022":   {"input": 3.00,   "output": 15.00},
    "claude-3-haiku-20240307":      {"input": 0.25,   "output": 1.25},
    "claude-3-5-haiku-20241022":    {"input": 0.80,   "output": 4.00},

    # ── Google ──
    "gemini-1.5-pro":       {"input": 1.25,   "output": 5.00},
    "gemini-1.5-flash":     {"input": 0.075,  "output": 0.30},

    "gemini-2.5-pro":       {"input": 1.25,   "output": 10.00},
    "gemini-2.5-flash":     {"input": 0.15,   "output": 0.60},

    # ── Local (free) ──
    "llama3":               {"input": 0.0,    "output": 0.0},
    "llama3.1":             {"input": 0.0,    "output": 0.0},
    "mistral":              {"input": 0.0,    "output": 0.0},
    "phi3":                 {"input": 0.0,    "output": 0.0},

    # ── Fallback (mock LLM) ──
    "_fallback":            {"input": 0.0,    "output": 0.0},
}


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text.
    Rule of thumb: ~4 chars per token for English, ~2 chars for Korean/CJK.
    """
    if not text:
        return 0

    cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff'
                    or '\uac00' <= c <= '\ud7af'
                    or '\u3040' <= c <= '\u30ff')

    ascii_chars = len(text) - cjk_chars

    # CJK: ~1.5 tokens per char, ASCII: ~0.25 tokens per char
    tokens = int(cjk_chars * 1.5 + ascii_chars * 0.25)
    return max(tokens, 1)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate exact cost in USD based on model and token counts.

    Args:
        model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-5")
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Cost in USD (float)
    """
    pricing = MODEL_PRICING.get(model)

    if not pricing:
        # Try partial match
        for key in MODEL_PRICING:
            if key in model or model in key:
                pricing = MODEL_PRICING[key]
                break

    if not pricing:
        pricing = MODEL_PRICING["_fallback"]
        logger.warning(f"Unknown model '{model}', using fallback pricing ($0)")

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total = input_cost + output_cost

    return round(total, 8)


def calculate_cost_from_text(model: str, input_text: str, output_text: str) -> dict:
    """
    Calculate cost from raw text (estimates tokens first).

    Returns:
        {
            "model": str,
            "input_tokens": int,
            "output_tokens": int,
            "total_tokens": int,
            "cost_usd": float,
            "cost_display": str
        }
    """
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    cost = calculate_cost(model, input_tokens, output_tokens)

    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost,
        "cost_display": format_cost(cost),
    }


def format_cost(cost_usd: float) -> str:
    """Format cost for display."""
    if cost_usd == 0:
        return "$0.0000"
    elif cost_usd < 0.01:
        return f"${cost_usd:.6f}"
    elif cost_usd < 1.0:
        return f"${cost_usd:.4f}"
    else:
        return f"${cost_usd:.2f}"


def get_model_pricing(model: str) -> dict:
    """Get pricing info for a specific model."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("_fallback"))
    return {
        "model": model,
        "input_per_1m": pricing["input"],
        "output_per_1m": pricing["output"],
        "input_per_1k": round(pricing["input"] / 1000, 6),
        "output_per_1k": round(pricing["output"] / 1000, 6),
    }


def list_all_models() -> list:
    """List all supported models with pricing."""
    result = []
    for model, pricing in MODEL_PRICING.items():
        if model.startswith("_"):
            continue
        provider = "local"
        if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
            provider = "openai"
        elif model.startswith("claude"):
            provider = "anthropic"
        elif model.startswith("gemini"):
            provider = "google"

        result.append({
            "model": model,
            "provider": provider,
            "input_per_1m": pricing["input"],
            "output_per_1m": pricing["output"],
        })
    return result


# ══════════════════════════════════════════════════════════════
#   Integrated Cost Tracker
# ══════════════════════════════════════════════════════════════

class CostTracker:
    """
    Tracks cumulative cost across a workflow execution.
    Thread-safe for concurrent agent steps.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.step_costs = []
        self._lock = __import__("threading").Lock()

    def record_step(self, agent: str, input_text: str, output_text: str,
                    duration_ms: int = 0) -> dict:
        """Record a single execution step and return cost info."""
        result = calculate_cost_from_text(self.model, input_text, output_text)

        with self._lock:
            self.total_input_tokens += result["input_tokens"]
            self.total_output_tokens += result["output_tokens"]
            self.total_cost += result["cost_usd"]

            step = {
                "agent": agent,
                "step_number": len(self.step_costs) + 1,
                "duration_ms": duration_ms,
                **result,
            }
            self.step_costs.append(step)

        return step

    def get_summary(self) -> dict:
        """Get overall cost summary."""
        with self._lock:
            return {
                "model": self.model,
                "total_steps": len(self.step_costs),
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens": self.total_input_tokens + self.total_output_tokens,
                "total_cost_usd": round(self.total_cost, 8),
                "total_cost_display": format_cost(self.total_cost),
                "steps": list(self.step_costs),
            }


logger.info("💰 [CostCalculator] Loaded pricing for %d models", len(MODEL_PRICING) - 1)
