"""Backward-compatible facade over the versioned model-cost contracts.

Production calls are charged by :mod:`model_transport`; ``deduct`` remains only
for one transition release and must not be called by the production pipeline.
"""

from pathlib import Path
from typing import Dict

from loguru import logger

from .model_accounting import (
    CanonicalTokenUsage,
    ModelPricingCatalog,
    calculate_actual_model_cost_usd,
)

class BudgetExhaustedError(Exception):
    """Raised when the DAG orchestrator has exceeded its hard cost limit."""
    pass

class PricingTable:
    """Exact compatibility lookup backed by Manifest pricing, never tags."""

    _RATES: Dict[str, Dict[str, float]] = {}
    _CATALOG: ModelPricingCatalog | None = None
    _POOL_PATH = (
        Path(__file__).resolve().parents[2]
        / "Pool"
        / "resources"
        / "json"
        / "combine.json"
    )

    @classmethod
    def catalog(cls) -> ModelPricingCatalog:
        if cls._CATALOG is None:
            cls._CATALOG = ModelPricingCatalog.from_manifest_file(cls._POOL_PATH)
        return cls._CATALOG
    
    @classmethod
    def get_rate(cls, model_name: str) -> Dict[str, float]:
        if model_name in cls._RATES:
            return cls._RATES[model_name]
            
        price = cls.catalog().resolve(model_ref=model_name)
        rates = {
            "input": float(price.input_per_m),
            "output": float(price.output_per_m),
            "cache": float(price.cache_per_m),
        }
        cls._RATES[model_name] = rates
        return rates

class GlobalBudgetManager:
    """Tracks the USD budget for a single pipeline run."""
    def __init__(self, max_budget_usd: float = 1.0):
        self.max_budget = max_budget_usd
        self.current_spend = 0.0
        self.is_exhausted = False
        logger.info(f"[BudgetManager] Activated Global Limit: ${self.max_budget:.4f}")

    def deduct(self, model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
        if self.is_exhausted:
            raise BudgetExhaustedError("System budget lock is active. Rejecting API call.")
            
        price = PricingTable.catalog().resolve(model_ref=model)
        usage = CanonicalTokenUsage(
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )
        cost = float(calculate_actual_model_cost_usd(usage, price))
        self.current_spend += cost
        logger.info(f"[Budget] Spent ${cost:.4f} on {model} (in: {input_tokens}, out: {output_tokens}, cache: {cached_tokens}). Total: ${self.current_spend:.4f}/${self.max_budget:.4f}")
        
        if self.current_spend >= self.max_budget:
            self.is_exhausted = True
            logger.warning(
                "[BudgetFacade] Limit reached after preserving the current response; "
                "a subsequent legacy deduct will be blocked."
            )
            
        return cost
