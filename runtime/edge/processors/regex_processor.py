"""Regex-based payload processor."""

import re
from typing import List

from entity.messages import Message
from utils.log_manager import LogManager
from .base import EdgePayloadProcessor, ProcessorFactoryContext
from entity.configs.edge.edge_processor import RegexEdgeProcessorConfig
from runtime.node.executor import ExecutionContext


class RegexEdgePayloadProcessor(EdgePayloadProcessor[RegexEdgeProcessorConfig]):
    def __init__(self, config: RegexEdgeProcessorConfig, ctx: ProcessorFactoryContext) -> None:
        super().__init__(config, ctx)
        flags = 0
        if not config.case_sensitive:
            flags |= re.IGNORECASE
        if config.multiline:
            flags |= re.MULTILINE
        if config.dotall:
            flags |= re.DOTALL
        self._pattern = re.compile(config.pattern, flags)
        self.label = f"regex({config.pattern})"
        self.metadata = {
            "pattern": config.pattern,
            "group": config.group,
            "multiple": config.multiple,
        }

    def transform(
        self,
        payload: Message,
        *,
        source_result: Message,
        from_node,
        edge_link,
        log_manager: LogManager,
        context: ExecutionContext,
    ) -> Message | None:
        matches = list(self._pattern.finditer(self._text(payload)))
        if not matches:
            return self._handle_no_match(payload, log_manager, from_node.id, edge_link.target.id)

        extracted = self._extract_values(matches)
        if not extracted:
            return self._handle_no_match(payload, log_manager, from_node.id, edge_link.target.id)

        cloned = payload.clone()
        if self.config.multiple:
            cloned.content = "\n".join(extracted)
        else:
            cloned.content = extracted[0]
        return cloned

    def _extract_values(self, matches: List[re.Match]) -> List[str]:
        values: List[str] = []
        for match in matches:
            group = self.config.group
            if group is None:
                value = match.group(0)
            else:
                value = match.group(group)
            if value is None:
                continue
            if self.config.template:
                value = self.config.template.replace("{match}", value)
            values.append(value)
            if not self.config.multiple:
                break
        return values

    def _handle_no_match(
        self,
        payload: Message,
        log_manager: LogManager,
        from_node_id: str,
        to_node_id: str,
    ) -> Message | None:
        behavior = self.config.on_no_match
        if behavior == "drop":
            log_manager.debug(
                f"Regex processor dropped payload for {from_node_id}->{to_node_id} (no match)"
            )
            return None
        if behavior == "default":
            default_value = self.config.default_value or ""
            cloned = payload.clone()
            cloned.content = default_value
            return cloned
        return payload

