# cost_calculator.py
# Token Cost Factor Auto-Calculation Module
# Formula: raw = W_in × P_in + W_cache × P_cache + W_out × P_out
# Output:  cost_factor = raw / max(all_raw)  ∈ (0, 1]
# Dynamic: EMA weight updates from actual token usage telemetry

from __future__ import annotations

import json
import os

# ─── Initial Weights ──────────────────────────
# Based on S-GAR pipeline token consumption analysis:
#   Input : Cache : Output ≈ 3 : 1 : 1
# These represent the relative token volume of each type in a typical agentic call.

DEFAULT_WEIGHTS = {
    "w_in":    3.0,    # Input tokens dominate (system prompt + accumulated context)
    "w_cache": 1.0,    # Cache hits from repeated system prompts
    "w_out":   1.0,    # Output tokens (artifact generation)
}

# EMA learning rate for dynamic weight updates
EMA_ALPHA = 0.1

# Minimum cost_factor to prevent division-by-zero in Advantage Score
MIN_COST_FACTOR = 0.01

# ─── Paths ────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_FILE  = os.path.join(_SCRIPT_DIR, "Pool", "index_meta", "cost_weights.json")
COMBINE_FILE  = os.path.join(_SCRIPT_DIR, "Pool", "resources", "json", "combine.json")


def load_weights() -> dict:
    """Load current weights from disk, or return defaults."""
    if os.path.exists(WEIGHTS_FILE):
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_WEIGHTS.copy()


def save_weights(weights: dict):
    """Persist current weights to disk."""
    os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
    with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2)


# ─── Core Calculation ─────────────────────────
def _resource_type(resource: dict) -> str:
    return (
        resource.get("resource_type")
        or resource.get("type", {}).get("resource_type")
        or ""
    )


def _as_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "n/a", "unknown"}:
        return None
    try:
        return float(text.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _normalize_pricing_dict(pricing: dict | None) -> dict | None:
    if not isinstance(pricing, dict):
        return None

    input_price = _as_float(pricing.get("input_per_m"))
    cache_price = _as_float(pricing.get("cache_per_m"))
    output_price = _as_float(pricing.get("output_per_m"))
    if input_price is None or cache_price is None or output_price is None:
        return None

    return {
        "input_per_m": input_price,
        "cache_per_m": cache_price,
        "output_per_m": output_price,
    }


def extract_pricing_from_tag(resource: dict) -> dict | None:
    """
    For Model-type resources, resource_tag convention is:
        [context_window, P_in, P_out, P_cache]
    
    e.g. ["128K Context", "0", "0", "0"]  (open-source, free)
    e.g. ["128K Context", "2.50", "10.00", "1.25"]  (GPT-4o)

    Returns pricing dict or None if not a Model or tags are missing.
    """
    if _resource_type(resource) != "Model":
        return None

    tags = resource.get("type", {}).get("resource_tag", [])
    if len(tags) < 4:
        return None

    input_price = _as_float(tags[1])
    output_price = _as_float(tags[2])
    cache_price = _as_float(tags[3])
    if input_price is None or output_price is None or cache_price is None:
        return None
    return {
        "input_per_m": input_price,
        "cache_per_m": cache_price,
        "output_per_m": output_price,
    }


def extract_model_pricing(resource: dict) -> dict | None:
    """
    Prefer Manifest.V1 type_specific.model.pricing. Fall back to legacy
    type.resource_tag[1:4] for old model records.
    """
    if _resource_type(resource) != "Model":
        return None

    model_block = resource.get("type_specific", {}).get("model", {})
    pricing = _normalize_pricing_dict(model_block.get("pricing"))
    if pricing is not None:
        return pricing
    return extract_pricing_from_tag(resource)


def compute_raw_cost(pricing: dict, weights: dict) -> float:
    """
    Compute the raw weighted cost index for a single model.

    pricing = {
        "input_per_m":  2.50,   # $/M input tokens
        "cache_per_m":  1.25,   # $/M cached tokens
        "output_per_m": 10.00   # $/M output tokens
    }
    """
    p_in    = pricing.get("input_per_m", 0.0)
    p_cache = pricing.get("cache_per_m", 0.0)
    p_out   = pricing.get("output_per_m", 0.0)

    raw = (weights["w_in"] * p_in
         + weights["w_cache"] * p_cache
         + weights["w_out"] * p_out)
    return raw


def normalize_cost_factors(resources: list[dict], weights: dict = None) -> list[dict]:
    """
    Compute and normalize token_cost_factor for all Model resources in-place.

    Reads pricing from type_specific.model.pricing for V1 Models and falls
    back to legacy resource_tag[1:4] when needed.
    Non-Model resources retain their existing cost_factor.

    Returns the modified resource list.
    """
    if weights is None:
        weights = load_weights()

    # Step 1: Compute raw costs for models with valid pricing data.
    raw_costs = {}
    for r in resources:
        pricing = extract_model_pricing(r)
        if pricing:
            raw = compute_raw_cost(pricing, weights)
            raw_costs[r["resource_id"]] = raw

    if not raw_costs:
        for r in resources:
            if _resource_type(r) == "Model":
                r.setdefault("utility", {})["token_cost_factor"] = max(
                    float(r.get("utility", {}).get("token_cost_factor", 0) or 0),
                    MIN_COST_FACTOR,
                )
        print("[cost_calculator] No models with pricing tags found; skipping cost_factor calculation")
        return resources

    # Step 2: Normalize to (0, 1] using max normalization
    max_raw = max(raw_costs.values())
    if max_raw <= 0:
        max_raw = 1.0  # Prevent division by zero

    print(f"[cost_calculator] Calculating cost_factor for {len(raw_costs)} models (max_raw={max_raw:.4f})")

    for r in resources:
        rid = r.get("resource_id")
        if not rid:
            continue
        if rid in raw_costs:
            raw = raw_costs[rid]
            factor = max(raw / max_raw, MIN_COST_FACTOR)
            r.setdefault("utility", {})["token_cost_factor"] = round(factor, 6)
            print(f"  {rid:<35} raw={raw:.4f} → factor={factor:.4f}")

    for r in resources:
        if _resource_type(r) == "Model" and r.get("resource_id") not in raw_costs:
            r.setdefault("utility", {})["token_cost_factor"] = max(
                float(r.get("utility", {}).get("token_cost_factor", 0) or 0),
                MIN_COST_FACTOR,
            )

    return resources


# ─── EMA Dynamic Weight Update ────────────────
def update_weights_ema(actual_usage: dict, weights: dict = None) -> dict:
    """
    Update weights using Exponential Moving Average based on actual token usage.

    actual_usage = {
        "input_tokens":  2340,
        "cache_tokens":  780,
        "output_tokens": 420,
    }

    Returns updated weights dict.
    """
    if weights is None:
        weights = load_weights()

    total = (actual_usage.get("input_tokens", 0)
           + actual_usage.get("cache_tokens", 0)
           + actual_usage.get("output_tokens", 0))

    if total <= 0:
        return weights

    # Observed ratios
    obs_in    = actual_usage["input_tokens"] / total
    obs_cache = actual_usage.get("cache_tokens", 0) / total
    obs_out   = actual_usage["output_tokens"] / total

    # Scale observed ratios to match current weight magnitude
    scale = weights["w_in"] + weights["w_cache"] + weights["w_out"]

    # EMA update
    alpha = EMA_ALPHA
    weights["w_in"]    = round((1 - alpha) * weights["w_in"]    + alpha * obs_in * scale, 4)
    weights["w_cache"] = round((1 - alpha) * weights["w_cache"] + alpha * obs_cache * scale, 4)
    weights["w_out"]   = round((1 - alpha) * weights["w_out"]   + alpha * obs_out * scale, 4)

    print(f"[cost_calculator] EMA weights updated: w_in={weights['w_in']}, "
          f"w_cache={weights['w_cache']}, w_out={weights['w_out']}")

    save_weights(weights)
    return weights


# ─── Standalone: Recalculate combine.json ─────
def recalculate_combine():
    """
    Read combine.json, recalculate all cost_factors, write back.
    Run this after adding new models or updating pricing.
    """
    with open(COMBINE_FILE, "r", encoding="utf-8") as f:
        resources = json.load(f)

    weights = load_weights()
    resources = normalize_cost_factors(resources, weights)

    with open(COMBINE_FILE, "w", encoding="utf-8") as f:
        json.dump(resources, f, indent=4, ensure_ascii=False)

    print(f"\n[cost_calculator] Updated cost_factor in combine.json")


if __name__ == "__main__":
    recalculate_combine()
