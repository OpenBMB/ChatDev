"""Loop timer guard node executor."""

import time
from typing import List, Dict, Any

from entity.configs import Node
from entity.configs.node.loop_timer import LoopTimerConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import NodeExecutor


class LoopTimerNodeExecutor(NodeExecutor):
    """Track loop duration and emit output only after hitting the time limit.

    Supports two modes:
    1. Standard Mode (passthrough=False): Suppresses input until time limit, then emits message
    2. Terminal Gate Mode (passthrough=True): Acts as a sequential switch
       - Before limit: Pass input through unchanged
       - At limit: Emit configured message, suppress original input
       - After limit: Transparent gate, pass all subsequent messages through
    """

    STATE_KEY = "loop_timer"

    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        config = node.as_config(LoopTimerConfig)
        if config is None:
            raise ValueError(f"Node {node.id} missing loop_timer configuration")

        state = self._get_state()
        timer_state = state.setdefault(node.id, {})

        # Initialize timer on first execution
        current_time = time.time()
        if "start_time" not in timer_state:
            timer_state["start_time"] = current_time
            timer_state["emitted"] = False

        start_time = timer_state["start_time"]
        elapsed_time = current_time - start_time

        # Convert max_duration to seconds based on unit
        max_duration_seconds = self._convert_to_seconds(
            config.max_duration, config.duration_unit
        )

        # Check if time limit has been reached
        limit_reached = elapsed_time >= max_duration_seconds

        # Terminal Gate Mode (passthrough=True)
        if config.passthrough:
            if not limit_reached:
                # Before limit: pass input through unchanged
                self.log_manager.debug(
                    f"LoopTimer {node.id}: {elapsed_time:.1f}s / {max_duration_seconds:.1f}s "
                    f"(passthrough mode: forwarding input)"
                )
                return inputs
            elif not timer_state["emitted"]:
                # At limit: emit configured message, suppress original input
                timer_state["emitted"] = True
                if config.reset_on_emit:
                    timer_state["start_time"] = current_time

                content = (
                    config.message
                    or f"Time limit reached ({config.max_duration} {config.duration_unit})"
                )
                metadata = {
                    "loop_timer": {
                        "elapsed_time": elapsed_time,
                        "max_duration": config.max_duration,
                        "duration_unit": config.duration_unit,
                        "reset_on_emit": config.reset_on_emit,
                        "passthrough": True,
                    }
                }

                self.log_manager.debug(
                    f"LoopTimer {node.id}: {elapsed_time:.1f}s / {max_duration_seconds:.1f}s "
                    f"(passthrough mode: emitting limit message)"
                )

                return [
                    Message(
                        role=MessageRole.ASSISTANT,
                        content=content,
                        metadata=metadata,
                    )
                ]
            else:
                # After limit: transparent gate, pass all subsequent messages through
                self.log_manager.debug(
                    f"LoopTimer {node.id}: {elapsed_time:.1f}s (passthrough mode: transparent gate)"
                )
                return inputs

        # Standard Mode (passthrough=False)
        if not limit_reached:
            self.log_manager.debug(
                f"LoopTimer {node.id}: {elapsed_time:.1f}s / {max_duration_seconds:.1f}s "
                f"(suppress downstream)"
            )
            return []

        if config.reset_on_emit and not timer_state["emitted"]:
            timer_state["start_time"] = current_time

        timer_state["emitted"] = True

        content = (
            config.message
            or f"Time limit reached ({config.max_duration} {config.duration_unit})"
        )
        metadata = {
            "loop_timer": {
                "elapsed_time": elapsed_time,
                "max_duration": config.max_duration,
                "duration_unit": config.duration_unit,
                "reset_on_emit": config.reset_on_emit,
                "passthrough": False,
            }
        }

        self.log_manager.debug(
            f"LoopTimer {node.id}: {elapsed_time:.1f}s / {max_duration_seconds:.1f}s "
            f"reached limit, releasing output"
        )

        return [
            Message(
                role=MessageRole.ASSISTANT,
                content=content,
                metadata=metadata,
            )
        ]

    def _get_state(self) -> Dict[str, Dict[str, Any]]:
        return self.context.global_state.setdefault(self.STATE_KEY, {})

    def _convert_to_seconds(self, duration: float, unit: str) -> float:
        """Convert duration to seconds based on unit."""
        unit_multipliers = {
            "seconds": 1.0,
            "minutes": 60.0,
            "hours": 3600.0,
        }
        return duration * unit_multipliers.get(unit, 1.0)
