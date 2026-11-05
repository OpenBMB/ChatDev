"""Immutable terminal failure facts shared by every formal pipeline stage."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from .pipeline_control import FrozenContract, canonical_sha256


TERMINAL_FAILURE_PROTOCOL = "sgar-terminal-failure-v1"
TerminalResponsibility = Literal[
    "framework", "infrastructure", "research", "budget", "interrupted"
]
TERMINAL_RESPONSIBILITY_SEVERITY = {
    "research": 0,
    "budget": 1,
    "infrastructure": 2,
    "interrupted": 3,
    "framework": 4,
}


class TerminalFailureError(RuntimeError):
    pass


class TerminalFailureEnvelope(FrozenContract):
    protocol: Literal[TERMINAL_FAILURE_PROTOCOL] = TERMINAL_FAILURE_PROTOCOL
    responsibility: TerminalResponsibility
    failure_stage: str = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    exception_type: str = ""
    retryable: bool = False
    response_received: bool = False
    run_id: str = ""
    graph_revision: int | None = None
    subtask_id: str = ""
    subtask_revision: int | None = None
    plan_revision: int | None = None
    step_id: str = ""
    request_sha256: str | None = None
    resource_call_id: str | None = None
    model_operation_id: str | None = None
    evaluation_operation_id: str | None = None
    source_event_ids: tuple[str, ...] = ()
    primary_failure_sha256: str | None = None
    message_sha256: str
    failure_sha256: str

    @field_validator(
        "message_sha256",
        "failure_sha256",
        "request_sha256",
        "primary_failure_sha256",
    )
    @classmethod
    def _validate_sha(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _validate_identity(self) -> "TerminalFailureEnvelope":
        projection = self.model_dump(mode="python", exclude={"failure_sha256"})
        if canonical_sha256(projection) != self.failure_sha256:
            raise ValueError("terminal_failure_sha256_mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        responsibility: str,
        failure_stage: str,
        failure_code: str,
        exception: BaseException | None = None,
        exception_type: str = "",
        retryable: bool = False,
        response_received: bool = False,
        run_id: str = "",
        graph_revision: int | None = None,
        subtask_id: str = "",
        subtask_revision: int | None = None,
        plan_revision: int | None = None,
        step_id: str = "",
        request_sha256: str | None = None,
        resource_call_id: str | None = None,
        model_operation_id: str | None = None,
        evaluation_operation_id: str | None = None,
        source_event_ids: Sequence[str] = (),
        primary_failure_sha256: str | None = None,
        message_sha256: str | None = None,
    ) -> "TerminalFailureEnvelope":
        normalized = str(responsibility)
        if normalized not in {
            "framework",
            "infrastructure",
            "research",
            "budget",
            "interrupted",
        }:
            raise TerminalFailureError("terminal_failure_responsibility_invalid")
        message_hash = message_sha256 or canonical_sha256(
            {
                "exception_type": exception_type or (
                    type(exception).__name__ if exception is not None else ""
                ),
                "failure_stage": failure_stage,
                "failure_code": failure_code,
            }
        )
        payload = {
            "protocol": TERMINAL_FAILURE_PROTOCOL,
            "responsibility": normalized,
            "failure_stage": str(failure_stage),
            "failure_code": str(failure_code),
            "exception_type": exception_type or (
                type(exception).__name__ if exception is not None else ""
            ),
            "retryable": bool(retryable),
            "response_received": bool(response_received),
            "run_id": str(run_id),
            "graph_revision": graph_revision,
            "subtask_id": str(subtask_id),
            "subtask_revision": subtask_revision,
            "plan_revision": plan_revision,
            "step_id": str(step_id),
            "request_sha256": request_sha256,
            "resource_call_id": resource_call_id,
            "model_operation_id": model_operation_id,
            "evaluation_operation_id": evaluation_operation_id,
            "source_event_ids": tuple(str(item) for item in source_event_ids),
            "primary_failure_sha256": primary_failure_sha256,
            "message_sha256": message_hash,
        }
        return cls(**payload, failure_sha256=canonical_sha256(payload))

    @property
    def run_status(self) -> str:
        return {
            "framework": "framework_failure",
            "infrastructure": "infrastructure_failure",
            "research": "research_failure",
            "budget": "budget_failure",
            "interrupted": "interrupted",
        }[self.responsibility]


def terminal_failure_from_mapping(
    value: Mapping[str, Any],
    **identity: Any,
) -> TerminalFailureEnvelope:
    return TerminalFailureEnvelope.create(
        responsibility=str(value.get("responsibility") or "framework"),
        failure_stage=str(value.get("failure_stage") or "failure_contract"),
        failure_code=str(value.get("failure_code") or "structured_failure_missing_code"),
        exception_type=str(value.get("exception_type") or ""),
        retryable=bool(value.get("retryable", False)),
        response_received=bool(value.get("response_received", False)),
        request_sha256=value.get("request_sha256") or value.get("request_hash"),
        resource_call_id=value.get("resource_call_id"),
        model_operation_id=value.get("model_operation_id"),
        evaluation_operation_id=value.get("evaluation_operation_id"),
        source_event_ids=tuple(value.get("source_event_ids") or ()),
        message_sha256=value.get("message_sha256"),
        **identity,
    )


def terminal_failure_from_execution_result(
    result: Any,
    **identity: Any,
) -> TerminalFailureEnvelope:
    metrics = getattr(result, "cost_metric", None)
    failure = metrics.get("failure") if isinstance(metrics, Mapping) else None
    if not isinstance(failure, Mapping):
        return TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="failure_contract",
            failure_code="formal_provider_failure_contract_missing",
            **identity,
        )
    return terminal_failure_from_mapping(failure, **identity)


def highest_severity_terminal_failure(
    failures: Sequence[TerminalFailureEnvelope],
) -> TerminalFailureEnvelope:
    """Select the terminal owner without replacing chronological first cause."""

    normalized = tuple(failures)
    if not normalized:
        raise TerminalFailureError("terminal_failure_selection_empty")
    if not all(isinstance(item, TerminalFailureEnvelope) for item in normalized):
        raise TerminalFailureError("terminal_failure_selection_invalid")
    return max(
        normalized,
        key=lambda item: TERMINAL_RESPONSIBILITY_SEVERITY[item.responsibility],
    )


__all__ = [
    "TERMINAL_FAILURE_PROTOCOL",
    "TERMINAL_RESPONSIBILITY_SEVERITY",
    "TerminalFailureEnvelope",
    "TerminalFailureError",
    "TerminalResponsibility",
    "highest_severity_terminal_failure",
    "terminal_failure_from_execution_result",
    "terminal_failure_from_mapping",
]
