"""KeywordEdgeManager implements declarative keyword conditions."""

import re

from entity.configs.edge.edge_condition import KeywordEdgeConditionConfig
from .base import ConditionFactoryContext
from .base import EdgeConditionManager
from ...node.executor import ExecutionContext


class KeywordEdgeConditionManager(EdgeConditionManager[KeywordEdgeConditionConfig]):
    def __init__(self, config: KeywordEdgeConditionConfig, ctx: ConditionFactoryContext, execution_context: ExecutionContext) -> None:
        super().__init__(config, ctx, execution_context)
        self.any_keywords = list(config.any_keywords)
        self.none_keywords = list(config.none_keywords)
        self.regex_patterns = list(config.regex_patterns)
        self.case_sensitive = bool(config.case_sensitive)
        self.default_value = bool(config.default)
        lowered_regex_flags = 0 if self.case_sensitive else re.IGNORECASE
        if self.case_sensitive:
            self.processed_any = self.any_keywords
            self.processed_none = self.none_keywords
        else:
            self.processed_any = [kw.lower() for kw in self.any_keywords]
            self.processed_none = [kw.lower() for kw in self.none_keywords]
        self.compiled_regex = [re.compile(pattern, lowered_regex_flags) for pattern in self.regex_patterns]
        self.label = f"keyword(any={len(self.any_keywords)}, none={len(self.none_keywords)}, regex={len(self.regex_patterns)})"
        self.metadata = {
            "any": self.any_keywords,
            "none": self.none_keywords,
            "regex": self.regex_patterns,
            "case_sensitive": self.case_sensitive,
            "default": self.default_value,
        }

    def _evaluate(self, data: str) -> bool:
        haystack = data if self.case_sensitive else data.lower()
        for keyword in self.processed_none:
            if keyword and keyword in haystack:
                return False
        for keyword in self.processed_any:
            if keyword and keyword in haystack:
                return True
        for pattern in self.compiled_regex:
            if pattern.search(data):
                return True
        if self.any_keywords or self.regex_patterns:
            return False
        return True

    def process(
        self,
        edge_link,
        source_result,
        from_node,
        log_manager,
    ) -> None:
        self._process_with_condition(
            self._evaluate,
            label=self.label,
            metadata=self.metadata,
            edge_link=edge_link,
            source_result=source_result,
            from_node=from_node,
            log_manager=log_manager,
        )
