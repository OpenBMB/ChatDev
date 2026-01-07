"""Split strategies for dynamic node execution.

Provides different methods to split input messages into execution units.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import List, Any, Optional

from entity.configs.dynamic_base import SplitConfig, RegexSplitConfig, JsonPathSplitConfig
from entity.messages import Message, MessageRole


class Splitter(ABC):
    """Abstract base class for input splitters."""

    @abstractmethod
    def split(self, inputs: List[Message]) -> List[List[Message]]:
        """Split inputs into execution units.
        
        Args:
            inputs: Input messages to split
            
        Returns:
            List of message groups, each group is one execution unit
        """
        pass


class MessageSplitter(Splitter):
    """Split by message - each message becomes one execution unit."""

    def split(self, inputs: List[Message]) -> List[List[Message]]:
        """Each input message becomes a separate unit."""
        return [[msg] for msg in inputs]


class RegexSplitter(Splitter):
    """Split by regex pattern matches."""

    def __init__(
        self,
        pattern: str,
        *,
        group: str | int | None = None,
        case_sensitive: bool = True,
        multiline: bool = False,
        dotall: bool = False,
        on_no_match: str = "pass",
    ):
        """Initialize with regex pattern and options.
        
        Args:
            pattern: Regex pattern to match
            group: Capture group name or index. Defaults to entire match (0).
            case_sensitive: Whether the regex should be case sensitive.
            multiline: Enable multiline mode (re.MULTILINE).
            dotall: Enable dotall mode (re.DOTALL).
            on_no_match: Behavior when no match is found ('pass' or 'empty').
        """
        flags = 0
        if not case_sensitive:
            flags |= re.IGNORECASE
        if multiline:
            flags |= re.MULTILINE
        if dotall:
            flags |= re.DOTALL
        
        self.pattern = re.compile(pattern, flags)
        self.group = group
        self.on_no_match = on_no_match

    def split(self, inputs: List[Message]) -> List[List[Message]]:
        """Split by finding all regex matches across all inputs."""
        units: List[List[Message]] = []
        
        for msg in inputs:
            text = msg.text_content()
            
            # Find all matches
            matches = list(self.pattern.finditer(text))
            
            if not matches:
                # Handle no match case
                if self.on_no_match == "pass":
                    units.append([msg])
                elif self.on_no_match == "empty":
                    # Return empty content
                    unit_msg = Message(
                        role=msg.role,
                        content="",
                        metadata={**msg.metadata, "split_source": "regex", "split_no_match": True},
                    )
                    units.append([unit_msg])
                continue
            
            for match in matches:
                # Extract the appropriate group
                if self.group is not None:
                    try:
                        match_text = match.group(self.group)
                    except (IndexError, re.error):
                        match_text = match.group(0)
                else:
                    match_text = match.group(0)
                
                if match_text is None:
                    match_text = ""
                
                unit_msg = Message(
                    role=msg.role,
                    content=match_text,
                    metadata={**msg.metadata, "split_source": "regex"},
                )
                units.append([unit_msg])
        
        return units if units else [[msg] for msg in inputs]


class JsonPathSplitter(Splitter):
    """Split by JSON array path extraction."""

    def __init__(self, json_path: str):
        """Initialize with JSON path.
        
        Args:
            json_path: Simple dot-notation path to array (e.g., 'items', 'data.results')
        """
        self.json_path = json_path

    def _extract_array(self, data: Any) -> List[Any]:
        """Extract array from data using simple dot notation path."""
        if not self.json_path:
            if isinstance(data, list):
                return data
            return [data]
            
        parts = self.json_path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return []
            
            if current is None:
                return []
        
        if isinstance(current, list):
            return current
        return [current]

    def split(self, inputs: List[Message]) -> List[List[Message]]:
        """Split by extracting array items from JSON content."""
        units: List[List[Message]] = []
        
        for msg in inputs:
            text = msg.text_content()
            
            # Try to parse as JSON
            try:
                data = json.loads(text)
                items = self._extract_array(data)
                
                for item in items:
                    if isinstance(item, (dict, list)):
                        content = json.dumps(item, ensure_ascii=False)
                    else:
                        content = str(item)
                    
                    unit_msg = Message(
                        role=msg.role,
                        content=content,
                        metadata={**msg.metadata, "split_source": "json_path"},
                    )
                    units.append([unit_msg])
                    
            except json.JSONDecodeError:
                # If not valid JSON, treat as single unit
                units.append([msg])
        
        return units if units else [[msg] for msg in inputs]


def create_splitter(
    split_type: str,
    pattern: Optional[str] = None,
    json_path: Optional[str] = None,
    *,
    group: str | int | None = None,
    case_sensitive: bool = True,
    multiline: bool = False,
    dotall: bool = False,
    on_no_match: str = "pass",
) -> Splitter:
    """Factory function to create appropriate splitter.
    
    Args:
        split_type: One of 'message', 'regex', 'json_path'
        pattern: Regex pattern (required for 'regex' type)
        json_path: JSON path (required for 'json_path' type)
        group: Capture group for regex (optional)
        case_sensitive: Case sensitivity for regex (default True)
        multiline: Multiline mode for regex (default False)
        dotall: Dotall mode for regex (default False)
        on_no_match: Behavior when no regex match ('pass' or 'empty')
        
    Returns:
        Configured Splitter instance
        
    Raises:
        ValueError: If required arguments are missing
    """
    if split_type == "message":
        return MessageSplitter()
    elif split_type == "regex":
        if not pattern:
            raise ValueError("regex splitter requires 'pattern' argument")
        return RegexSplitter(
            pattern,
            group=group,
            case_sensitive=case_sensitive,
            multiline=multiline,
            dotall=dotall,
            on_no_match=on_no_match,
        )
    elif split_type == "json_path":
        if not json_path:
            raise ValueError("json_path splitter requires 'json_path' argument")
        return JsonPathSplitter(json_path)
    else:
        raise ValueError(f"Unknown split type: {split_type}")


def create_splitter_from_config(split_config: "SplitConfig") -> Splitter:
    """Create a splitter from a SplitConfig object.
    
    Args:
        split_config: The split configuration
        
    Returns:
        Configured Splitter instance
    """
    if split_config.type == "message":
        return MessageSplitter()
    elif split_config.type == "regex":
        regex_config = split_config.as_split_config(RegexSplitConfig)
        if not regex_config:
            raise ValueError("Invalid regex split configuration")
        return RegexSplitter(
            regex_config.pattern,
            group=regex_config.group,
            case_sensitive=regex_config.case_sensitive,
            multiline=regex_config.multiline,
            dotall=regex_config.dotall,
            on_no_match=regex_config.on_no_match,
        )
    elif split_config.type == "json_path":
        json_config = split_config.as_split_config(JsonPathSplitConfig)
        if not json_config:
            raise ValueError("Invalid json_path split configuration")
        return JsonPathSplitter(json_config.json_path)
    else:
        raise ValueError(f"Unknown split type: {split_config.type}")


def group_messages(messages: List[Message], group_size: int) -> List[List[Message]]:
    """Group messages into batches for tree reduction.
    
    Args:
        messages: Messages to group
        group_size: Target size per group
        
    Returns:
        List of message groups. Last group may have fewer items.
    """
    if not messages:
        return []
    
    groups: List[List[Message]] = []
    for i in range(0, len(messages), group_size):
        groups.append(messages[i:i + group_size])
    
    return groups