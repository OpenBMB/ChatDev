"""Token usage tracking module for DevAll project."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TokenUsage:
    """Stores token usage metrics for individual API calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    node_id: str | None = None
    model_name: str | None = None
    workflow_id: str | None = None
    provider: str | None = None  # Add provider field

    def __post_init__(self):
        try:
            self.input_tokens = max(0, int(self.input_tokens or 0))
        except (ValueError, TypeError):
            self.input_tokens = 0

        try:
            self.output_tokens = max(0, int(self.output_tokens or 0))
        except (ValueError, TypeError):
            self.output_tokens = 0

        if self.total_tokens is None or self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
        else:
            try:
                self.total_tokens = max(0, int(self.total_tokens))
            except (ValueError, TypeError):
                self.total_tokens = self.input_tokens + self.output_tokens

        if self.metadata is None or not isinstance(self.metadata, dict):
            if hasattr(self.metadata, "__iter__") and not isinstance(
                self.metadata, (str, bytes)
            ):
                try:
                    self.metadata = dict(self.metadata)
                except (ValueError, TypeError):
                    self.metadata = {}
            else:
                self.metadata = {}

    def to_dict(self):
        """Convert to dictionary format."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.isoformat()
            if isinstance(self.timestamp, datetime)
            else str(self.timestamp),
            "node_id": self.node_id,
            "model_name": self.model_name,
            "workflow_id": self.workflow_id,
            "provider": self.provider,  # Include provider in output
        }


class TokenTracker:
    """Singleton class to track token usage across a workflow."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.total_usage = TokenUsage(workflow_id=workflow_id)
        self.node_usages = defaultdict(TokenUsage)
        self.model_usages = defaultdict(TokenUsage)
        self.call_history = []
        self.node_call_counts = defaultdict(
            int
        )  # Track how many times each node is called

    def record_usage(
        self,
        node_id: str,
        model_name: str,
        usage: TokenUsage,
        provider: str | None = None,
    ):
        """Records token usage for a specific call, handling multiple node executions."""
        if usage is None:
            return
        if isinstance(usage, dict):
            usage = TokenUsage(**usage)
        elif not isinstance(usage, TokenUsage):
            raise TypeError(f"Expected TokenUsage or dict, got {type(usage).__name__}")

        node_id = str(node_id or "default")
        model_name = str(model_name or "default")

        # Update the usage with provider if it wasn't set already
        if provider and not usage.provider:
            usage.provider = provider

        # Add to total usage
        self.total_usage.input_tokens += usage.input_tokens
        self.total_usage.output_tokens += usage.output_tokens
        self.total_usage.total_tokens += usage.total_tokens

        # Add to node-specific usage
        node_usage = self.node_usages[node_id]
        node_usage.node_id = node_id
        node_usage.input_tokens += usage.input_tokens
        node_usage.output_tokens += usage.output_tokens
        node_usage.total_tokens += usage.total_tokens
        if provider:
            node_usage.provider = provider  # Store provider info

        # Add to model-specific usage
        model_usage = self.model_usages[model_name]
        model_usage.model_name = model_name
        model_usage.input_tokens += usage.input_tokens
        model_usage.output_tokens += usage.output_tokens
        model_usage.total_tokens += usage.total_tokens
        if provider:
            model_usage.provider = provider  # Store provider info

        # Increment call count for this node
        self.node_call_counts[node_id] += 1

        # Add to call history
        history_entry = {
            "node_id": node_id,
            "model_name": model_name,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "metadata": dict(usage.metadata),
            "timestamp": usage.timestamp.isoformat()
            if isinstance(usage.timestamp, datetime)
            else str(usage.timestamp),
            "execution_number": self.node_call_counts[
                node_id
            ],  # Track which execution this is
        }

        # Add provider to history entry if available
        if provider:
            history_entry["provider"] = provider

        self.call_history.append(history_entry)

    def get_total_usage(self) -> TokenUsage:
        """Get total token usage for the workflow."""
        return self.total_usage

    def get_node_usage(self, node_id: str) -> TokenUsage:
        """Get token usage for a specific node (across all its executions)."""
        if node_id in self.node_usages:
            return self.node_usages[node_id]
        return TokenUsage(node_id=node_id, workflow_id=self.workflow_id)

    def get_model_usage(self, model_name: str) -> TokenUsage:
        """Get token usage for a specific model."""
        if model_name in self.model_usages:
            return self.model_usages[model_name]
        return TokenUsage(model_name=model_name, workflow_id=self.workflow_id)

    def get_node_execution_count(self, node_id: str) -> int:
        """Get how many times a node was executed."""
        return self.node_call_counts.get(node_id, 0)

    def reset(self) -> None:
        """Reset all tracked usage and history."""
        self.total_usage = TokenUsage(workflow_id=self.workflow_id)
        self.node_usages.clear()
        self.model_usages.clear()
        self.call_history.clear()
        self.node_call_counts.clear()

    def get_token_usage(self) -> dict[str, Any]:
        data = {
            "workflow_id": self.workflow_id,
            "total_usage": {
                "input_tokens": self.total_usage.input_tokens,
                "output_tokens": self.total_usage.output_tokens,
                "total_tokens": self.total_usage.total_tokens,
            },
            "node_usages": {
                node_id: {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                }
                for node_id, usage in self.node_usages.items()
            },
            "model_usages": {
                model_name: {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                }
                for model_name, usage in self.model_usages.items()
            },
            "node_execution_counts": dict(self.node_call_counts),
            "call_history": self.call_history,
        }
        return data

    def export_to_file(self, filepath: str):
        """Export token usage data to a JSON file."""
        import json
        from pathlib import Path

        # Create directory if it doesn't exist
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = self.get_token_usage()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
