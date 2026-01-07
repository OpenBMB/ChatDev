"""Core message abstractions used across providers and executors."""

import copy
from dataclasses import dataclass, field
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MessageRole(str, Enum):
    """Unified message roles for internal conversations."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageBlockType(str, Enum):
    """Supported block types for multimodal message content."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    DATA = "data"

    @classmethod
    def from_mime_type(cls, mime_type: str) -> "MessageBlockType":
        """Guess block type from MIME type."""
        if not mime_type:
            return MessageBlockType.FILE
        if mime_type.startswith("image/"):
            return MessageBlockType.IMAGE
        if mime_type.startswith("audio/"):
            return MessageBlockType.AUDIO
        if mime_type.startswith("video/"):
            return MessageBlockType.VIDEO
        return MessageBlockType.FILE


@dataclass
class AttachmentRef:
    """Metadata for a payload stored locally or uploaded to a provider."""

    attachment_id: str
    mime_type: Optional[str] = None
    name: Optional[str] = None
    size: Optional[int] = None
    sha256: Optional[str] = None
    local_path: Optional[str] = None
    remote_file_id: Optional[str] = None
    data_uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "attachment_id": self.attachment_id,
            "mime_type": self.mime_type,
            "name": self.name,
            "size": self.size,
            "sha256": self.sha256,
            "local_path": self.local_path,
            "remote_file_id": self.remote_file_id,
            "metadata": dict(self.metadata),
        }
        if include_data and self.data_uri:
            payload["data_uri"] = self.data_uri
        elif self.data_uri and not include_data:
            payload["data_uri"] = "[omitted]"
        # Remove keys that are None to keep payload compact
        return {key: value for key, value in payload.items() if value is not None and value != {}}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttachmentRef":
        return cls(
            attachment_id=data.get("attachment_id", ""),
            mime_type=data.get("mime_type"),
            name=data.get("name"),
            size=data.get("size"),
            sha256=data.get("sha256"),
            local_path=data.get("local_path"),
            remote_file_id=data.get("remote_file_id"),
            data_uri=data.get("data_uri"),
            metadata=data.get("metadata") or {},
        )

    def copy(self) -> "AttachmentRef":
        return AttachmentRef(
            attachment_id=self.attachment_id,
            mime_type=self.mime_type,
            name=self.name,
            size=self.size,
            sha256=self.sha256,
            local_path=self.local_path,
            remote_file_id=self.remote_file_id,
            data_uri=self.data_uri,
            metadata=dict(self.metadata),
        )


@dataclass
class MessageBlock:
    """Single block of multimodal content."""

    type: MessageBlockType
    text: Optional[str] = None
    attachment: Optional[AttachmentRef] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": self.type.value,
        }
        if self.text is not None:
            payload["text"] = self.text
        if self.attachment:
            payload["attachment"] = self.attachment.to_dict(include_data=include_data)
        if self.data:
            payload["data"] = self.data
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageBlock":
        raw_type = data.get("type") or MessageBlockType.TEXT.value
        try:
            block_type = MessageBlockType(raw_type)
        except ValueError:
            block_type = MessageBlockType.DATA
        attachment_data = data.get("attachment")
        attachment = None
        if isinstance(attachment_data, dict):
            attachment = AttachmentRef.from_dict(attachment_data)
        return cls(
            type=block_type,
            text=data.get("text"),
            attachment=attachment,
            data=data.get("data") or {},
        )

    @classmethod
    def text_block(cls, text: str) -> "MessageBlock":
        return cls(type=MessageBlockType.TEXT, text=text)

    def describe(self) -> str:
        """Human-friendly summary for logging."""
        if self.type is MessageBlockType.TEXT and self.text:
            return self.text
        if self.attachment:
            name = self.attachment.name or self.attachment.attachment_id
            return f"[{self.type.value} attachment: {name}]"
        if self.text:
            return self.text
        if "text" in self.data:
            return str(self.data["text"])
        return f"[{self.type.value} block]"

    def copy(self) -> "MessageBlock":
        return MessageBlock(
            type=self.type,
            text=self.text,
            attachment=self.attachment.copy() if self.attachment else None,
            data=dict(self.data),
        )


@dataclass
class ToolCallPayload:
    """Unified representation of a tool call request."""

    id: str
    function_name: str
    arguments: str
    type: str = "function"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_openai_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible schema."""
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function_name,
                "arguments": self.arguments,
            },
        }


@dataclass
class FunctionCallOutputEvent:
    """Structured event recorded when a tool execution finishes."""

    call_id: str
    function_name: Optional[str] = None
    output_blocks: List[MessageBlock] = field(default_factory=list)
    output_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return "function_call_output"

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": self.type,
            "call_id": self.call_id,
        }
        if self.function_name:
            payload["function_name"] = self.function_name
        if self.output_blocks:
            payload["output_blocks"] = [
                block.to_dict(include_data=include_data) for block in self.output_blocks
            ]
        if self.output_text is not None:
            payload["output"] = self.output_text
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def has_blocks(self) -> bool:
        return bool(self.output_blocks)

    def describe(self) -> str:
        if self.output_text:
            return self.output_text
        if self.output_blocks:
            descriptions = [block.describe() for block in self.output_blocks]
            return "\n".join(filter(None, descriptions))
        return ""


MessageContent = Union[str, List[MessageBlock], List[Dict[str, Any]]]


@dataclass
class Message:
    """Unified message structure shared by executors and providers."""

    role: MessageRole
    content: MessageContent
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[ToolCallPayload] = field(default_factory=list)
    keep: bool = False
    preserve_role: bool = False

    def with_content(self, content: MessageContent) -> "Message":
        """Return a shallow copy with updated content."""
        return Message(
            role=self.role,
            content=content,
            name=self.name,
            tool_call_id=self.tool_call_id,
            metadata=dict(self.metadata),
            tool_calls=list(self.tool_calls),
            keep=self.keep,
            preserve_role=self.preserve_role,
        )

    def with_role(self, role: MessageRole) -> "Message":
        """Return a shallow copy with updated role."""
        return Message(
            role=role,
            content=self.content,
            name=self.name,
            tool_call_id=self.tool_call_id,
            metadata=dict(self.metadata),
            tool_calls=list(self.tool_calls),
            keep=self.keep,
            preserve_role=self.preserve_role,
        )

    def text_content(self) -> str:
        """Best-effort string representation of the content."""
        if self.content is None:
            return ""
        if isinstance(self.content, str):
            return self.content
        # Some providers (e.g., multimodal) return list content; join textual parts.
        parts = []
        for block in self.blocks():
            description = block.describe()
            if description:
                parts.append(description)
        return "\n".join(parts)

    def blocks(self) -> List[MessageBlock]:
        """Return content as a list of MessageBlock items."""
        if self.content is None:
            return []
        if isinstance(self.content, str):
            return [MessageBlock.text_block(self.content)]
        blocks: List[MessageBlock] = []
        for block in self.content:
            if isinstance(block, MessageBlock):
                blocks.append(block)
            elif isinstance(block, dict):
                try:
                    blocks.append(MessageBlock.from_dict(block))
                except Exception:
                    # Fallback to text representation of unexpected dicts
                    text_value = block.get("text") if isinstance(block, dict) else None
                    blocks.append(MessageBlock(MessageBlockType.DATA, text=text_value, data=block if isinstance(block, dict) else {}))
        return blocks

    def clone(self) -> "Message":
        """Deep copy of the message, preserving content blocks."""
        return Message(
            role=self.role,
            content=_copy_content(self.content),
            name=self.name,
            tool_call_id=self.tool_call_id,
            metadata=dict(self.metadata),
            tool_calls=list(self.tool_calls),
            keep=self.keep,
            preserve_role=self.preserve_role,
        )

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        payload = {
            "role": self.role.value,
        }
        if isinstance(self.content, list):
            payload["content"] = [
                block.to_dict(include_data=include_data) if isinstance(block, MessageBlock) else block for block in self.content
            ]
        else:
            payload["content"] = self.content
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.metadata:
            payload["metadata"] = self.metadata
        if self.tool_calls:
            payload["tool_calls"] = [call.to_openai_dict() for call in self.tool_calls]
        if self.keep:
            payload["keep"] = self.keep
        if self.preserve_role:
            payload["preserve_role"] = self.preserve_role
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        role_value = data.get("role")
        if not role_value:
            raise ValueError("message dict missing role")
        role = MessageRole(role_value)
        content = data.get("content")
        if isinstance(content, list):
            converted: List[MessageBlock] = []
            for block in content:
                if isinstance(block, MessageBlock):
                    converted.append(block)
                elif isinstance(block, dict):
                    try:
                        converted.append(MessageBlock.from_dict(block))
                    except Exception:
                        # Preserve raw dict for debugging; text_content will stringify best-effort
                        converted.append(
                            MessageBlock(
                                type=MessageBlockType.DATA,
                                text=str(block),
                                data=block,
                            )
                        )
            content = converted
        tool_calls_data = data.get("tool_calls") or []
        tool_calls: List[ToolCallPayload] = []
        for item in tool_calls_data:
            if not isinstance(item, dict):
                continue
            fn = item.get("function", {}) or {}
            metadata = item.get("metadata") or {}
            tool_calls.append(
                ToolCallPayload(
                    id=item.get("id", ""),
                    function_name=fn.get("name", ""),
                    arguments=fn.get("arguments", ""),
                    type=item.get("type", "function"),
                    metadata=metadata,
                )
            )
        return cls(
            role=role,
            content=content,
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            metadata=data.get("metadata") or {},
            tool_calls=tool_calls,
            keep=bool(data.get("keep", False)),
            preserve_role=bool(data.get("preserve_role", False)),
        )


def serialize_messages(messages: List[Message], *, include_data: bool = True) -> str:
    """Serialize message list into JSON string."""
    return json.dumps([msg.to_dict(include_data=include_data) for msg in messages], ensure_ascii=False)


def deserialize_messages(payload: str) -> List[Message]:
    """Deserialize JSON string back to messages."""
    if not payload:
        return []
    raw = json.loads(payload)
    if not isinstance(raw, list):
        raise ValueError("message payload must be a list")
    return [Message.from_dict(item) for item in raw if isinstance(item, dict)]


def _copy_content(content: MessageContent) -> MessageContent:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    copied: List[Any] = []
    for block in content:
        if isinstance(block, MessageBlock):
            copied.append(block.copy())
        else:
            copied.append(copy.deepcopy(block))
    return copied
