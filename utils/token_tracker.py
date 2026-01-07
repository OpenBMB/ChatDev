"""Token usage tracking module for DevAll project."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict


@dataclass
class TokenUsage:
    """Stores token usage metrics for individual API calls."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    node_id: Optional[str] = None
    model_name: Optional[str] = None
    workflow_id: Optional[str] = None
    provider: Optional[str] = None  # Add provider field

    def to_dict(self):
        """Convert to dictionary format."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "model_name": self.model_name,
            "workflow_id": self.workflow_id,
            "provider": self.provider  # Include provider in output
        }


class TokenTracker:
    """Singleton class to track token usage across a workflow."""
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.total_usage = TokenUsage()
        self.node_usages = defaultdict(TokenUsage)
        self.model_usages = defaultdict(TokenUsage)
        self.call_history = []
        self.node_call_counts = defaultdict(int)  # Track how many times each node is called

    def record_usage(self, node_id: str, model_name: str, usage: TokenUsage, provider: str = None):
        """Records token usage for a specific call, handling multiple node executions."""
        # Update the usage with provider if it wasn't set already
        if provider and not usage.provider:
            usage.provider = provider
            
        # Add to total usage
        self.total_usage.input_tokens += usage.input_tokens
        self.total_usage.output_tokens += usage.output_tokens
        self.total_usage.total_tokens += usage.total_tokens
        
        # Add to node-specific usage
        node_usage = self.node_usages[node_id]
        node_usage.input_tokens += usage.input_tokens
        node_usage.output_tokens += usage.output_tokens
        node_usage.total_tokens += usage.total_tokens
        if provider:
            node_usage.provider = provider  # Store provider info
        
        # Add to model-specific usage
        model_usage = self.model_usages[model_name]
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
            "timestamp": usage.timestamp.isoformat(),
            "execution_number": self.node_call_counts[node_id]  # Track which execution this is
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
        return self.node_usages[node_id]

    def get_model_usage(self, model_name: str) -> TokenUsage:
        """Get token usage for a specific model."""
        return self.model_usages[model_name]

    def get_node_execution_count(self, node_id: str) -> int:
        """Get how many times a node was executed."""
        return self.node_call_counts[node_id]

    def get_token_usage(self) -> Dict[str, Any]:
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
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
