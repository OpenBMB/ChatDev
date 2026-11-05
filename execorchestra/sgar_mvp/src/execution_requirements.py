"""Compiler-declared execution needs, separate from a Tool's static needs."""

from typing import Any, Mapping

from pydantic import Field, model_serializer

from .pipeline_control import FrozenContract


class ExecutionNetworkDeclaration(FrozenContract):
    execution_network_required: bool | None = Field(
        default=None,
        description=(
            "Set true on a Tool step or callable when its bound program or operation "
            "needs network access. Omit for unchanged manifest requirements; false "
            "does not disable a manifest's required network or override task policy."
        ),
    )

    @model_serializer(mode="wrap")
    def _serialize_execution_requirement(self, handler: Any) -> dict[str, Any]:
        result = handler(self)
        if self.execution_network_required is None:
            result.pop("execution_network_required", None)
        return result


def requires_execution_network(requirements: Mapping[str, Any], declaration: Any) -> bool:
    network = requirements.get("network")
    return bool(
        requirements.get("network_required")
        or (isinstance(network, Mapping) and network.get("required"))
        or getattr(declaration, "execution_network_required", False)
    )
