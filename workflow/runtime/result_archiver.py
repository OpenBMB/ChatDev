"""Utilities for persisting execution artifacts."""

from utils.log_manager import LogManager
from utils.token_tracker import TokenTracker
from workflow.graph_context import GraphContext


class ResultArchiver:
    """Handles post-execution persistence (tokens, logs, metadata)."""

    def __init__(
        self,
        graph: GraphContext,
        log_manager: LogManager,
        token_tracker: TokenTracker,
    ) -> None:
        self.graph = graph
        self.log_manager = log_manager
        self.token_tracker = token_tracker

    def export(self, final_result: str) -> None:
        token_usage_path = self.graph.directory / f"token_usage_{self.graph.name}.json"
        self.token_tracker.export_to_file(str(token_usage_path))
        self.log_manager.record_workflow_end(
            success=True,
            details={
                "token_usage": self.token_tracker.get_token_usage(),
                "final_result": final_result,
            },
        )
        log_file_path = self.graph.directory / "execution_logs.json"
        self.log_manager.save_logs(str(log_file_path))
