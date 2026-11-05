"""Pure official-price calculation, shared by runtime and offline repricing.

Full tariffs stay out of compiler prompts. Resource manifests materialize the
three reference rates and a copy of the applicable versioned billing rule.
"""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
import json


class IncompleteOfficialPricing(ValueError):
    pass


def load_official_pricebook(path: str | Path | None = None) -> dict[str, Any]:
    target=Path(path) if path else Path(__file__).resolve().parents[1]/'config/official_model_prices.json'
    return json.loads(target.read_text(encoding='utf-8'))


def effective_rates(rule: Mapping[str, Any], input_tokens: int) -> dict[str, Any]:
    rates=dict(rule)
    for tier in sorted(rule.get('input_tiers',[]),key=lambda t:t['above_input_tokens']):
        if input_tokens > tier['above_input_tokens']:
            rates.update(tier)
    return rates


def official_token_cost(rule: Mapping[str, Any], *, input_tokens: int,
                        output_tokens: int, cached_input_tokens: int = 0,
                        cache_write_input_tokens: int = 0,
                        cache_write_1h_input_tokens: int = 0,
                        cache_read_mode: str = 'implicit',
                        tier_input_tokens: int | None = None) -> Decimal:
    """Input includes read/write tokens; write_1h is a subset of write_total.

    tier_input_tokens is only for homogeneous historical request groups, whose
    aggregate token sum must not be interpreted as one long-context request.
    """
    counts=(input_tokens,output_tokens,cached_input_tokens,cache_write_input_tokens,cache_write_1h_input_tokens)
    if any(type(v) is not int or v < 0 for v in counts):
        raise ValueError('invalid_billing_token_count')
    if cached_input_tokens+cache_write_input_tokens > input_tokens or cache_write_1h_input_tokens > cache_write_input_tokens:
        raise ValueError('cache_components_exceed_input')
    rates=effective_rates(rule,input_tokens if tier_input_tokens is None else tier_input_tokens)
    cache_key='explicit_cache_per_m' if cache_read_mode=='explicit' and 'explicit_cache_per_m' in rates else 'cache_per_m'
    parts=[(input_tokens-cached_input_tokens-cache_write_input_tokens,'input_per_m'),
           (cached_input_tokens,cache_key),
           (cache_write_input_tokens-cache_write_1h_input_tokens,'cache_write_per_m'),
           (cache_write_1h_input_tokens,'cache_write_1h_per_m'),
           (output_tokens,'output_per_m')]
    amount=Decimal(0)
    for count,key in parts:
        if not count:continue
        value=rates.get(key)
        if value is None:raise IncompleteOfficialPricing('official_rate_unavailable:'+key)
        amount+=Decimal(count)*Decimal(str(value))
    return amount/Decimal(1_000_000)
