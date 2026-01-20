"""OpenAI provider implementation."""

import base64
import hashlib

import binascii
import os
from typing import Any, Dict, List, Optional, Union
from urllib.parse import unquote_to_bytes

import openai
from openai import OpenAI

from entity.messages import (
    AttachmentRef,
    FunctionCallOutputEvent,
    Message,
    MessageBlock,
    MessageBlockType,
    MessageRole,
    ToolCallPayload,
)
from entity.tool_spec import ToolSpec
from runtime.node.agent import ModelProvider
from runtime.node.agent import ModelResponse
from utils.token_tracker import TokenUsage


class OpenAIProvider(ModelProvider):
    """OpenAI provider implementation."""

    CSV_INLINE_CHAR_LIMIT = 200_000  # safeguard large attachments
    TEXT_INLINE_CHAR_LIMIT = 200_000  # safeguard large text/* attachments
    MAX_INLINE_FILE_BYTES = 50 * 1024 * 1024  # OpenAI function output limit (~50 MB)

    def create_client(self):
        """
        Create and return the OpenAI client.
        
        Returns:
            OpenAI client instance with token tracking if available
        """
        if self.base_url:
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            return OpenAI(
                api_key=self.api_key,
            )

    def call_model(
        self,
        client: openai.Client,
        conversation: List[Message],
        timeline: List[Any],
        tool_specs: Optional[List[ToolSpec]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Call the OpenAI model with the given messages and parameters.
        """
        # 1. Determine if we should use Chat Completions directly
        is_chat = self._is_chat_completions_mode(client)
        
        if is_chat:
            request_payload = self._build_chat_payload(conversation, tool_specs, kwargs)
            response = client.chat.completions.create(**request_payload)
            self._track_token_usage(response)
            self._append_chat_response_output(timeline, response)
            message = self._deserialize_chat_response(response)
            return ModelResponse(message=message, raw_response=response)

        # 2. Try Responses API with fallback
        request_payload = self._build_request_payload(timeline, tool_specs, kwargs)
        try:
            response = client.responses.create(**request_payload)
            self._track_token_usage(response)
            self._append_response_output(timeline, response)
            message = self._deserialize_response(response)
            return ModelResponse(message=message, raw_response=response)
        except Exception as e:
            new_request_payload = self._build_chat_payload(conversation, tool_specs, kwargs)
            response = client.chat.completions.create(**new_request_payload)
            self._track_token_usage(response)
            self._append_chat_response_output(timeline, response)
            message = self._deserialize_chat_response(response)
            return ModelResponse(message=message, raw_response=response)

    def _is_chat_completions_mode(self, client: Any) -> bool:
        """Determine if we should use standard chat completions instead of responses API."""
        protocol = self.params.get("protocol")
        if protocol == "chat":
            return True
        if protocol == "responses":
            return False
        # Default to Responses API only if it exists on the client
        return not hasattr(client, "responses")

    def extract_token_usage(self, response: Any) -> TokenUsage:
        """
        Extract token usage from the OpenAI API response.
        
        Args:
            response: OpenAI API response from the model call
            
        Returns:
            TokenUsage instance with token counts
        """
        usage = getattr(response, "usage", None)
        if not usage:
            return TokenUsage()

        def _get(name: str) -> Any:
            if hasattr(usage, name):
                return getattr(usage, name)
            if isinstance(usage, dict):
                return usage.get(name)
            return None

        prompt_tokens = _get("prompt_tokens")
        completion_tokens = _get("completion_tokens")
        input_tokens = _get("input_tokens")
        output_tokens = _get("output_tokens")

        resolved_input = input_tokens if input_tokens is not None else prompt_tokens or 0
        resolved_output = output_tokens if output_tokens is not None else completion_tokens or 0

        total_tokens = _get("total_tokens")
        if total_tokens is None:
            total_tokens = (resolved_input or 0) + (resolved_output or 0)

        metadata = {
            "prompt_tokens": prompt_tokens or 0,
            "completion_tokens": completion_tokens or 0,
            "input_tokens": resolved_input or 0,
            "output_tokens": resolved_output or 0,
            "total_tokens": total_tokens or 0,
        }

        return TokenUsage(
            input_tokens=resolved_input or 0,
            output_tokens=resolved_output or 0,
            total_tokens=total_tokens or 0,
            metadata=metadata,
        )

    def _track_token_usage(self, response: Any) -> None:
        """Record token usage if a tracker is attached to the config."""
        token_tracker = getattr(self.config, "token_tracker", None)
        if not token_tracker:
            return

        usage = self.extract_token_usage(response)
        if usage.input_tokens == 0 and usage.output_tokens == 0 and not usage.metadata:
            return

        node_id = getattr(self.config, "node_id", "ALL")
        usage.node_id = node_id
        usage.model_name = self.model_name
        usage.workflow_id = token_tracker.workflow_id
        usage.provider = "openai"

        token_tracker.record_usage(node_id, self.model_name, usage, provider="openai")

    def _build_request_payload(
        self,
        timeline: List[Any],
        tool_specs: Optional[List[ToolSpec]],
        raw_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construct the Responses API payload from event timeline."""
        params = dict(raw_params)
        max_tokens = params.pop("max_tokens", None)
        max_output_tokens = params.pop("max_output_tokens", None)
        if max_output_tokens is None and max_tokens is not None:
            max_output_tokens = max_tokens

        input_messages: List[Any] = []
        for item in timeline:
            serialized = self._serialize_timeline_item(item)
            if serialized is not None:
                input_messages.append(serialized)

        if not input_messages:
            input_messages = [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": ""}],
                }
            ]

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "input": input_messages,
            "temperature": params.pop("temperature", 0.7),
            "timeout": params.pop("timeout", 300),  # 5 min
        }
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        elif self.params.get("max_output_tokens"):
            payload["max_output_tokens"] = self.params["max_output_tokens"]

        user_tools = params.pop("tools", None)
        merged_tools: List[Any] = []
        if isinstance(user_tools, list):
            merged_tools.extend(user_tools)
        elif user_tools is not None:
            raise ValueError("params.tools must be a list when provided")

        if tool_specs:
            merged_tools.extend(spec.to_openai_dict() for spec in tool_specs)

        if merged_tools:
            payload["tools"] = merged_tools

        tool_choice = params.pop("tool_choice", None)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        elif tool_specs:
            payload.setdefault("tool_choice", "auto")

        # Pass any remaining kwargs directly
        payload.update(params)
        return payload

    def _build_chat_payload(
        self,
        conversation: List[Message],
        tool_specs: Optional[List[ToolSpec]],
        raw_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construct standard Chat Completions API payload."""
        params = dict(raw_params)
        max_output_tokens = params.pop("max_output_tokens", None)
        max_tokens = params.pop("max_tokens", None)
        if max_tokens is None and max_output_tokens is not None:
            max_tokens = max_output_tokens

        messages: List[Any] = []
        for item in conversation:
            serialized = self._serialize_message_for_chat(item)
            if serialized is not None:
                messages.append(serialized)

        if not messages:
            messages = [{"role": "user", "content": ""}]

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": params.pop("temperature", 0.7),
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        elif self.params.get("max_tokens"):
             payload["max_tokens"] = self.params["max_tokens"]

        user_tools = params.pop("tools", None)
        merged_tools: List[Any] = []
        if isinstance(user_tools, list):
            merged_tools.extend(user_tools)

        if tool_specs:
            for spec in tool_specs:
                merged_tools.append({
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters or {"type": "object", "properties": {}},
                    }
                })

        if merged_tools:
            payload["tools"] = merged_tools

        tool_choice = params.pop("tool_choice", None)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        elif tool_specs:
            payload.setdefault("tool_choice", "auto")

        payload.update(params)
        return payload

    def _serialize_timeline_item_for_chat(self, item: Any) -> Optional[Any]:
        if isinstance(item, Message):
            return self._serialize_message_for_chat(item)
        if isinstance(item, FunctionCallOutputEvent):
            return self._serialize_function_call_output_event_for_chat(item)
        if isinstance(item, dict):
             # basic conversion if it looks like a Responses output
             role = item.get("role")
             content = item.get("content")
             tool_calls = item.get("tool_calls")
             if role and (content or tool_calls):
                  return {
                       "role": role,
                       "content": self._transform_blocks_for_chat(content) if isinstance(content, list) else content,
                       "tool_calls": tool_calls
                  }
        return None

    def _serialize_message_for_chat(self, message: Message) -> Dict[str, Any]:
        """Convert internal Message to standard Chat Completions schema."""
        role_value = message.role.value
        blocks = message.blocks()
        if not blocks or message.role == MessageRole.TOOL:
            content = message.text_content()
        else:
            content = self._transform_blocks_for_chat(self._serialize_blocks(blocks, message.role))

        payload: Dict[str, Any] = {
            "role": role_value,
            "content": content,
        }
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [tc.to_openai_dict() for tc in message.tool_calls]
        return payload

    def _serialize_function_call_output_event_for_chat(self, event: FunctionCallOutputEvent) -> Dict[str, Any]:
        """Convert tool result to standard Chat Completions schema."""
        text = event.output_text or ""
        if event.output_blocks:
             # simple concatenation for tool output in chat mode
             text = "\n".join(b.describe() for b in event.output_blocks)
        
        return {
            "role": "tool",
            "tool_call_id": event.call_id or "tool_call",
            "content": text,
        }

    def _transform_blocks_for_chat(self, blocks: List[Dict[str, Any]]) -> Union[str, List[Dict[str, Any]]]:
        """Convert Responses block types to Chat block types (e.g., input_text -> text)."""
        transformed: List[Dict[str, Any]] = []
        for block in blocks:
            b_type = block.get("type", "")
            if b_type in ("input_text", "output_text"):
                transformed.append({"type": "text", "text": block.get("text", "")})
            elif b_type in ("input_image", "output_image"):
                transformed.append({"type": "image_url", "image_url": {"url": block.get("image_url", "")}})
            else:
                # Keep as is or drop if complex
                transformed.append(block)
        
        # If only one text block, return as string for better compatibility
        if len(transformed) == 1 and transformed[0]["type"] == "text":
            return transformed[0]["text"]
        return transformed

    def _deserialize_chat_response(self, response: Any) -> Message:
        """Convert Chat Completions output to internal Message."""
        choices = self._get_attr(response, "choices") or []
        if not choices:
            return Message(role=MessageRole.ASSISTANT, content="")
            
        choice = choices[0]
        msg = self._get_attr(choice, "message")
        
        tool_calls: List[ToolCallPayload] = []
        tc_data = self._get_attr(msg, "tool_calls")
        if tc_data:
            for idx, tc in enumerate(tc_data):
                f_data = self._get_attr(tc, "function") or {}
                function_name = self._get_attr(f_data, "name") or ""
                arguments = self._get_attr(f_data, "arguments") or ""
                if not isinstance(arguments, str):
                    arguments = str(arguments)
                call_id = self._get_attr(tc, "id")
                if not call_id:
                    call_id = self._build_tool_call_id(function_name, arguments, fallback_prefix=f"tool_call_{idx}")
                tool_calls.append(ToolCallPayload(
                    id=call_id,
                    function_name=function_name,
                    arguments=arguments,
                    type="function"
                ))
        
        return Message(
            role=MessageRole.ASSISTANT,
            content=self._get_attr(msg, "content") or "",
            tool_calls=tool_calls
        )

    def _append_chat_response_output(self, timeline: List[Any], response: Any) -> None:
        """Add chat response to timeline, preserving tool_calls (Chat API compatible)."""
        msg = response.choices[0].message
        assistant_msg = {
            "role": "assistant",
            "content": msg.content or ""
        }

        if getattr(msg, "tool_calls", None):
            assistant_msg["tool_calls"] = []
            for idx, tc in enumerate(msg.tool_calls):
                function_name = tc.function.name
                arguments = tc.function.arguments or ""
                if not isinstance(arguments, str):
                    arguments = str(arguments)
                call_id = tc.id or self._build_tool_call_id(function_name, arguments, fallback_prefix=f"tool_call_{idx}")
                assistant_msg["tool_calls"].append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": arguments,
                    },
                })

        timeline.append(assistant_msg)

    def _serialize_timeline_item(self, item: Any) -> Optional[Any]:
        if isinstance(item, Message):
            return self._serialize_message_for_responses(item)
        if isinstance(item, FunctionCallOutputEvent):
            return self._serialize_function_call_output_event(item)
        return item

    def _serialize_message_for_responses(self, message: Message) -> Dict[str, Any]:
        """Convert internal Message to Responses input schema."""
        role_value = message.role.value
        content_blocks = self._serialize_content_blocks(message)
        payload: Dict[str, Any] = {
            "role": role_value,
            "content": content_blocks,
        }
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        return payload

    def _serialize_content_blocks(self, message: Message) -> List[Dict[str, Any]]:
        blocks = message.blocks()
        if not blocks:
            text = message.text_content()
            block_type = "output_text" if message.role is MessageRole.ASSISTANT else "input_text"
            return [{"type": block_type, "text": text}]

        return self._serialize_blocks(blocks, message.role)

    def _serialize_blocks(self, blocks: List[MessageBlock], role: MessageRole) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        for block in blocks:
            serialized.append(self._serialize_block(block, role))
        return serialized

    def _serialize_block(self, block: MessageBlock, role: MessageRole) -> Dict[str, Any]:
        if block.type is MessageBlockType.TEXT:
            content_type = "output_text" if role is MessageRole.ASSISTANT else "input_text"
            return {
                "type": content_type,
                "text": block.text or "",
            }

        attachment = block.attachment
        if block.type is MessageBlockType.IMAGE:
            media_type = "output_image" if role is MessageRole.ASSISTANT else "input_image"
            return self._serialize_media_block(media_type, attachment)
        if block.type is MessageBlockType.AUDIO:
            media_type = "output_audio" if role is MessageRole.ASSISTANT else "input_audio"
            return self._serialize_media_block(media_type, attachment)
        if block.type is MessageBlockType.VIDEO:
            media_type = "output_video" if role is MessageRole.ASSISTANT else "input_video"
            return self._serialize_media_block(media_type, attachment)
        if block.type is MessageBlockType.FILE:
            inline_text = self._maybe_inline_text_file(block)
            if inline_text is not None:
                content_type = "output_text" if role is MessageRole.ASSISTANT else "input_text"
                return {
                    "type": content_type,
                    "text": inline_text,
                }
            return self._serialize_file_block(attachment, block)

        # Fallback: treat as text/data
        return {
            "type": "input_text",
            "text": block.describe(),
        }

    def _serialize_media_block(
        self,
        media_type: str,
        attachment: Optional[AttachmentRef],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"type": media_type}
        if not attachment:
            return payload

        url_key = {
            "input_image": "image_url",
            "output_image": "image_url",
            "input_audio": "audio_url",
            "output_audio": "audio_url",
            "input_video": "video_url",
            "output_video": "video_url",
        }.get(media_type)

        if attachment.remote_file_id:
            payload["file_id"] = attachment.remote_file_id
        elif attachment.data_uri and url_key:
            payload[url_key] = attachment.data_uri
        elif attachment.local_path and url_key:
            payload[url_key] = self._make_data_uri_from_path(attachment.local_path, attachment.mime_type)
        return payload

    def _serialize_file_block(
        self,
        attachment: Optional[AttachmentRef],
        block: MessageBlock,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"type": "input_file"}
        if attachment:
            if attachment.remote_file_id:
                payload["file_id"] = attachment.remote_file_id
            else:
                data_uri = attachment.data_uri
                if not data_uri and attachment.local_path:
                    data_uri = self._make_data_uri_from_path(attachment.local_path, attachment.mime_type)
                if data_uri:
                    payload["file_data"] = data_uri
                else:
                    raise ValueError("Attachment missing file_id or data for input_file block")
            if attachment.name:
                payload["filename"] = attachment.name
        else:
            raise ValueError("File block requires an attachment reference")
        return payload

    def _maybe_inline_text_file(self, block: MessageBlock) -> Optional[str]:
        """Inline local text/* attachments to avoid unsupported file-type uploads."""

        attachment = block.attachment
        if not attachment:
            return None

        mime = (attachment.mime_type or "").lower()
        name = (attachment.name or "").lower()
        is_json = mime in {
            "application/json",
            "application/jsonl",
            "application/x-ndjson",
            "application/ndjson",
        } or name.endswith((".json", ".jsonl", ".ndjson"))
        if not (mime.startswith("text/") or is_json):
            return None
        if attachment.remote_file_id:
            return None  # nothing to inline if already remote-only

        text = self._read_attachment_text(attachment)
        if text is None:
            return None

        is_csv = "text/csv" in mime or name.endswith(".csv")
        limit_attr = "csv_inline_char_limit" if is_csv else "text_inline_char_limit"
        default_limit = self.CSV_INLINE_CHAR_LIMIT if is_csv else self.TEXT_INLINE_CHAR_LIMIT
        limit = getattr(self, limit_attr, default_limit)
        truncated = False
        if len(text) > limit:
            text = text[:limit]
            truncated = True

        display_name = attachment.name or attachment.attachment_id or ("attachment.csv" if is_csv else "attachment.txt")
        suffix = "\n\n[truncated after %d characters]" % limit if truncated else ""
        if is_csv:
            return f"CSV file '{display_name}':\n{text}{suffix}"
        mime_display = attachment.mime_type or "text/*"
        return f"Text file '{display_name}' ({mime_display}):\n```text\n{text}\n```{suffix}"

    def _maybe_inline_csv(self, block: MessageBlock) -> Optional[str]:
        """Backward compatible alias for older call sites/tests."""
        return self._maybe_inline_text_file(block)

    def _read_attachment_text(self, attachment: AttachmentRef) -> Optional[str]:
        data_bytes: Optional[bytes] = None
        if attachment.data_uri:
            data_bytes = self._decode_data_uri(attachment.data_uri)
        elif attachment.local_path and os.path.exists(attachment.local_path):
            try:
                with open(attachment.local_path, "rb") as handle:
                    data_bytes = handle.read()
            except OSError:
                return None
        if data_bytes is None:
            return None
        try:
            return data_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return data_bytes.decode("utf-8", errors="replace")

    def _decode_data_uri(self, data_uri: str) -> Optional[bytes]:
        if not data_uri.startswith("data:"):
            return None
        header, _, data = data_uri.partition(",")
        if not _:
            return None
        if ";base64" in header:
            try:
                return base64.b64decode(data)
            except (ValueError, binascii.Error):
                return None
        return unquote_to_bytes(data)

    def _deserialize_response(self, response: Any) -> Message:
        """Convert Responses API output to internal Message."""
        output_blocks = getattr(response, "output", []) or []
        assistant_blocks: List[MessageBlock] = []
        tool_calls: List[ToolCallPayload] = []

        for item in output_blocks:
            item_type = self._get_attr(item, "type")
            if item_type == "message":
                role_value = self._get_attr(item, "role") or "assistant"
                if role_value != "assistant":
                    continue
                content_items = self._get_attr(item, "content") or []
                parsed_blocks, parsed_calls = self._parse_output_content(content_items)
                assistant_blocks.extend(parsed_blocks)
                tool_calls.extend(parsed_calls)
            elif item_type == "image_generation_call":
                assistant_blocks.append(self._parse_image_generation_call(item))
            elif item_type in {"tool_call", "function_call"}:
                parsed_call = self._parse_tool_call(item)
                if parsed_call:
                    tool_calls.append(parsed_call)

        if not assistant_blocks:
            fallback_text = self._extract_fallback_text(response)
            if fallback_text:
                assistant_blocks.append(MessageBlock(MessageBlockType.TEXT, text=fallback_text))

        return Message(
            role=MessageRole.ASSISTANT,
            content=assistant_blocks or "",
            tool_calls=tool_calls,
        )

    def _extract_fallback_text(self, response: Any) -> Optional[str]:
        """Return the concatenated output text without triggering Responses errors."""
        output = getattr(response, "output", None)
        if not output:
            return None
        try:
            return getattr(response, "output_text", None)
        except TypeError:
            # OpenAI SDK raises TypeError when output is None; treat as missing text
            return None
        except AttributeError:
            return None

    def _parse_output_content(
        self,
        content_items: List[Any],
    ) -> tuple[List[MessageBlock], List[ToolCallPayload]]:
        blocks: List[MessageBlock] = []
        tool_calls: List[ToolCallPayload] = []
        for part in content_items:
            part_type = self._get_attr(part, "type")
            if part_type in {"output_text", "text"}:
                blocks.append(MessageBlock(MessageBlockType.TEXT, text=self._get_attr(part, "text") or ""))
            elif part_type in {"output_image", "image"}:
                blocks.append(
                    MessageBlock(
                        type=MessageBlockType.IMAGE,
                        attachment=AttachmentRef(
                            attachment_id=self._get_attr(part, "id") or "",
                            data_uri=self._get_attr(part, "image_base64"),
                            metadata=self._get_attr(part, "metadata") or {},
                        ),
                    )
                )
            elif part_type in {"tool_call", "function_call"}:
                parsed = self._parse_tool_call(part)
                if parsed:
                    tool_calls.append(parsed)
            else:
                blocks.append(
                    MessageBlock(
                        type=MessageBlockType.DATA,
                        text=str(self._get_attr(part, "text") or ""),
                        data=self._maybe_to_dict(part),
                    )
                )
        return blocks, tool_calls

    def _parse_image_generation_call(self, payload: Any) -> MessageBlock:
        status = self._get_attr(payload, "status") or ""
        if status != "completed":
            raise RuntimeError(f"Image generation call not completed (status={status})")
        image_b64 = self._get_attr(payload, "result")
        if not image_b64:
            raise RuntimeError("Image generation call returned empty result")
        attachment_id = self._get_attr(payload, "id") or ""
        data_uri = f"data:image/png;base64,{image_b64}"
        return MessageBlock(
            type=MessageBlockType.IMAGE,
            attachment=AttachmentRef(
                attachment_id=attachment_id,
                data_uri=data_uri,
                metadata={"source": "image_generation_call"},
            ),
        )

    def _parse_tool_call(self, payload: Any) -> Optional[ToolCallPayload]:
        function_payload = self._get_attr(payload, "function") or {}
        function_name = self._get_attr(function_payload, "name") or self._get_attr(payload, "name") or ""
        arguments = self._get_attr(function_payload, "arguments") or self._get_attr(payload, "arguments") or ""
        if not function_name:
            return None
        if isinstance(arguments, (dict, list)):
            try:
                import json

                arguments_str = json.dumps(arguments, ensure_ascii=False)
            except Exception:
                arguments_str = str(arguments)
        else:
            arguments_str = str(arguments)
        call_id = self._get_attr(payload, "call_id") or self._get_attr(payload, "id") or ""
        if not call_id:
            call_id = self._build_tool_call_id(function_name, arguments_str)
        return ToolCallPayload(
            id=call_id,
            function_name=function_name,
            arguments=arguments_str,
            type="function",
        )

    def _build_tool_call_id(self, function_name: str, arguments: str, *, fallback_prefix: str = "tool_call") -> str:
        base = function_name or fallback_prefix
        payload = f"{base}:{arguments or ''}".encode("utf-8")
        digest = hashlib.md5(payload).hexdigest()[:8]
        return f"{base}_{digest}"

    def _get_attr(self, payload: Any, key: str) -> Any:
        if hasattr(payload, key):
            return getattr(payload, key)
        if isinstance(payload, dict):
            return payload.get(key)
        return None

    def _maybe_to_dict(self, payload: Any) -> Dict[str, Any]:
        if hasattr(payload, "model_dump"):
            try:
                return payload.model_dump()
            except Exception:
                return {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _make_data_uri_from_path(self, path: str, mime_type: Optional[str]) -> str:
        mime = mime_type or "application/octet-stream"
        file_size = os.path.getsize(path)
        if file_size > self.MAX_INLINE_FILE_BYTES:
            raise ValueError(
                f"Attachment '{path}' is {file_size} bytes; exceeds inline limit of {self.MAX_INLINE_FILE_BYTES} bytes"
            )
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    def _serialize_function_call_output_event(
        self,
        event: FunctionCallOutputEvent,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": event.type,
            "call_id": event.call_id or event.function_name or "tool_call",
        }
        if event.output_blocks:
            payload["output"] = self._serialize_blocks(event.output_blocks, MessageRole.TOOL)
        else:
            text = event.output_text or ""
            payload["output"] = [
                {
                    "type": "input_text",
                    "text": text,
                }
            ]
        return payload

    def _append_response_output(self, timeline: List[Any], response: Any) -> None:
        output = getattr(response, "output", None)
        if not output:
            return
        timeline.extend(output)
