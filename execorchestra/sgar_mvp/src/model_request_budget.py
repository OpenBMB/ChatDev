"""Run-scoped timing policy, separate from provider and request identities.

Adapters supply a monotonic deadline; retry owners manage attempts remaining.
Neither changes the model payload, selects another model, or resets the run clock.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
import math
import time

from .model_accounting import BudgetControlError


class ModelTimeBudgetError(BudgetControlError):
    error_code = "model_time_budget_exhausted"


class ModelAttemptTimeout(TimeoutError):
    error_code = "model_attempt_timeout"
    provider_execution_unknown = True


@dataclass(frozen=True)
class ModelRequestBudget:
    deadline_monotonic: float | None = None
    # A benchmark deadline (when present) owns the request window. Otherwise
    # the configured provider transport timeout applies; SGAR adds no shorter
    # per-request deadline of its own.
    execution_timeout_seconds: float | None = None
    control_timeout_seconds: float | None = None
    downstream_reserve_seconds: float = 60.0
    # A single unresponsive provider request must not consume every model-capable
    # phase that remains in the benchmark window.  The share is applied to the
    # live usable window, so longer cases retain proportionally longer calls.
    max_attempt_fraction: float = 0.5
    minimum_attempt_seconds: float = 15.0

    def __post_init__(self):
        for value in (self.execution_timeout_seconds, self.control_timeout_seconds,
                      self.minimum_attempt_seconds):
            if value is None:
                continue
            if not math.isfinite(value) or value <= 0:
                raise ValueError("model_request_timeout_invalid")
        if (not math.isfinite(self.downstream_reserve_seconds)
                or self.downstream_reserve_seconds < 0):
            raise ValueError("model_request_reserve_invalid")
        if (not math.isfinite(self.max_attempt_fraction)
                or not 0 < self.max_attempt_fraction <= 1):
            raise ValueError("model_request_attempt_fraction_invalid")
        if self.deadline_monotonic is not None and not math.isfinite(self.deadline_monotonic):
            raise ValueError("model_request_deadline_invalid")

    def attempt_timeout(
        self,
        stage: str,
        attempts_remaining: int = 1,
        recovery_routes_remaining: int = 1,
        completion_window: bool = False,
    ) -> float | None:
        timeout = (self.execution_timeout_seconds
                   if stage in {"model_execution", "agent_execution"}
                   else self.control_timeout_seconds)
        if self.deadline_monotonic is not None:
            available = (self.deadline_monotonic - time.monotonic()
                         - self.downstream_reserve_seconds)
            route_fraction = 1.0 / (max(1, recovery_routes_remaining) + 1)
            attempt_window = available * min(
                self.max_attempt_fraction,
                route_fraction,
            )
            if (stage in {"model_execution", "agent_execution"}
                    and attempt_window < 2 * self.minimum_attempt_seconds
                    and (completion_window or available < 4 * self.minimum_attempt_seconds)):
                # In the final usable minute, repeated fractional reservation
                # can cancel the current action before it produces any output.
                # Allow that action the live window, as for a closing audit.
                # Keep the absolute deadline, downstream publication reserve,
                # explicit provider cap and all acceptance/retry rules intact.
                attempt_window = available
            if attempt_window < self.minimum_attempt_seconds:
                raise ModelTimeBudgetError(
                    "No admissible model attempt remains before the downstream reserve"
                )
            # Preserve a model-capable window for recovery or final synthesis.
            # This cap changes only transport timing; it never reduces the
            # provider's output-token allowance or mutates the request payload.
            timeout = (
                min(timeout, attempt_window)
                if timeout is not None
                else attempt_window
            )
        return timeout

    def record(self) -> dict:
        return {"protocol": "sgar-model-request-budget-v4", **asdict(self),
                "completion_window_policy": "late_materialized_evidence_audit_preserves_downstream_reserve",
                "late_execution_window_policy": "use_available_below_four_minimum_attempt_windows"}


_ACTIVE_BUDGET: ContextVar[ModelRequestBudget | None] = ContextVar("model_request_budget", default=None)
_ATTEMPTS_REMAINING: ContextVar[int] = ContextVar("model_attempts_remaining", default=1)
_RECOVERY_ROUTES_REMAINING: ContextVar[int] = ContextVar(
    "model_recovery_routes_remaining",
    default=1,
)
_COMPLETION_WINDOW: ContextVar[bool] = ContextVar("model_completion_window", default=False)


@contextmanager
def model_request_budget(budget: ModelRequestBudget):
    token = _ACTIVE_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_BUDGET.reset(token)


@contextmanager
def model_attempts_remaining(attempts: int):
    token = _ATTEMPTS_REMAINING.set(max(1, attempts))
    try:
        yield
    finally:
        _ATTEMPTS_REMAINING.reset(token)


@contextmanager
def model_recovery_routes_remaining(routes: int):
    """Reserve provider time for each still-admissible execution route."""

    token = _RECOVERY_ROUTES_REMAINING.set(max(1, int(routes)))
    try:
        yield
    finally:
        _RECOVERY_ROUTES_REMAINING.reset(token)


def current_attempt_timeout(stage: str = "") -> float | None:
    budget = _ACTIVE_BUDGET.get()
    return (budget.attempt_timeout(
                stage,
                _ATTEMPTS_REMAINING.get(),
                _RECOVERY_ROUTES_REMAINING.get(),
                _COMPLETION_WINDOW.get(),
            )
            if budget is not None else None)


@contextmanager
def model_completion_window(enabled: bool):
    """Scope closing-audit timing to one turn; never change its model payload."""
    token = _COMPLETION_WINDOW.set(bool(enabled))
    try:
        yield
    finally:
        _COMPLETION_WINDOW.reset(token)


def current_tool_timeout(declared_seconds: int | float | str | None = None) -> int:
    """Use the task window for unspecified Tool timeouts, retaining explicit caps.

    Tool execution is not a provider attempt: it must not inherit the model
    retry fraction. Keep the existing finalization reserve and the original
    default for callers with no task deadline. The adapter still owns the
    absolute task deadline; this function never extends it.
    """
    declared = int(declared_seconds) if declared_seconds is not None else None
    if declared is not None and not 1 <= declared <= 1800:
        raise ValueError("manifest_execution_timeout_invalid")
    budget = _ACTIVE_BUDGET.get()
    if budget is not None and budget.deadline_monotonic is not None:
        remaining = max(1, int(budget.deadline_monotonic - time.monotonic()
                               - budget.downstream_reserve_seconds))
        return min(declared, remaining) if declared is not None else remaining
    return declared if declared is not None else 180


def require_retry_time(delay_seconds: float) -> None:
    budget = _ACTIVE_BUDGET.get()
    if budget is not None and budget.deadline_monotonic is not None:
        available = (budget.deadline_monotonic - time.monotonic()
                     - budget.downstream_reserve_seconds)
        if available < delay_seconds + budget.minimum_attempt_seconds:
            raise ModelTimeBudgetError("Insufficient time for retry backoff and another attempt")
