"""Gemini provider implementation."""

import base64
import binascii
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from google import genai
from google.genai import types as genai_types
from google.genai.types import GenerateContentResponse

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


class GeminiProvider(ModelProvider):
    """Gemini provider implementation."""

    CSV_INLINE_CHAR_LIMIT = 200_000
    CSV_INLINE_SIZE_THRESHOLD_BYTES = 3 * 1024 * 1024  # 3 MB

    def create_client(self):
        """
        Create and return the Gemini client.
        """
        client_kwargs: Dict[str, Any] = {}
        if self.api_key:
            client_kwargs["api_key"] = self.api_key

        base_url = (self.base_url or "").strip()
        http_options = self._build_http_options(base_url)
        if http_options:
            client_kwargs["http_options"] = http_options

        return genai.Client(**client_kwargs)

    def call_model(
        self,
        client,
        conversation: List[Message],
        timeline: List[Any],
        tool_specs: Optional[List[ToolSpec]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Call the Gemini model using the unified conversation timeline.
        """
        contents, system_instruction = self._build_contents(timeline)
        config = self._build_generation_config(system_instruction, tool_specs, kwargs)
        # print(contents)
        # print(config)

        response: GenerateContentResponse = client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        # print(response)

        self._track_token_usage(response)
        self._append_response_contents(timeline, response)
        message = self._deserialize_response(response)
        return ModelResponse(message=message, raw_response=response)

    def extract_token_usage(self, response: Any) -> TokenUsage:
        """Extract token usage from Gemini usage metadata."""
        usage_metadata = getattr(response, "usage_metadata", None)
        if not usage_metadata:
            return TokenUsage()

        prompt_tokens = getattr(usage_metadata, "prompt_token_count", None) or 0
        candidate_tokens = getattr(usage_metadata, "candidates_token_count", None) or 0
        total_tokens = getattr(usage_metadata, "total_token_count", None)
        cached_tokens = getattr(usage_metadata, "cached_content_token_count", None)

        metadata = {
            "prompt_token_count": prompt_tokens,
            "candidates_token_count": candidate_tokens,
        }
        if total_tokens is not None:
            metadata["total_token_count"] = total_tokens
        if cached_tokens is not None:
            metadata["cached_content_token_count"] = cached_tokens

        return TokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=candidate_tokens,
            total_tokens=total_tokens or (prompt_tokens + candidate_tokens),
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # Serialization helpers
    # ---------------------------------------------------------------------

    def _build_contents(
        self,
        timeline: List[Any],
    ) -> Tuple[List[genai_types.Content], Optional[str]]:
        contents: List[genai_types.Content] = []
        system_prompts: List[str] = []

        for item in timeline:
            if isinstance(item, Message):
                if item.role is MessageRole.SYSTEM:
                    text = item.text_content().strip()
                    if text:
                        system_prompts.append(text)
                    continue
                contents.append(self._message_to_content(item))
                continue

            if isinstance(item, FunctionCallOutputEvent):
                contents.append(self._function_output_event_to_content(item))
                continue

            if isinstance(item, genai_types.Content):
                contents.append(item)

        if not contents:
            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text="")],
                )
            )

        system_instruction = "\n\n".join(system_prompts) if system_prompts else None
        return contents, system_instruction

    def _append_response_contents(self, timeline: List[Any], response: Any) -> None:
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content:
                timeline.append(content)

    def _message_to_content(self, message: Message) -> genai_types.Content:
        role = self._map_role(message.role)
        if message.role is MessageRole.TOOL:
            part = self._build_tool_response_part(message)
            return genai_types.Content(role="user", parts=[part])

        parts: List[genai_types.Part] = []
        for block in message.blocks():
            parts.extend(self._block_to_parts(block))
        if not parts:
            text = message.text_content()
            parts.append(genai_types.Part(text=text))
        return genai_types.Content(role=role, parts=parts)

    def _function_output_event_to_content(
        self,
        event: FunctionCallOutputEvent,
    ) -> genai_types.Content:
        function_name = event.function_name or event.call_id or "tool"
        payload: Dict[str, Any] = {}
        function_result_parts: List[genai_types.FunctionResponsePart] = []
        result_texts: List[str] = []

        if event.output_blocks:
            for block in event.output_blocks:
                # Describe the block for the text result
                desc = self._describe_block(block)
                if desc:
                    result_texts.append(desc)

                if self._block_has_attachment(block):
                    # Check if we should inline this attachment as text
                    if self._should_inline_attachment_as_text(block):
                        text_content = self._read_attachment_text(block.attachment)
                        if text_content:
                            result_texts.append(f"\n[Attachment Content: {block.attachment.name}]\n{text_content}")
                        continue

                    # Otherwise treat as binary part
                    general_parts = self._block_to_parts(block)
                    function_result_parts.extend(self._general_parts_to_function_response_parts(general_parts))
        else:
            if event.output_text:
                result_texts.append(event.output_text)

        payload["result"] = "\n".join(result_texts)

        function_part = genai_types.Part.from_function_response(
            name=function_name,
            response=payload or {"result": ""},
            parts=function_result_parts or None
        )

        parts: List[genai_types.Part] = [function_part]
        return genai_types.Content(role="user", parts=parts)

    def _should_inline_attachment_as_text(self, block: MessageBlock) -> bool:
        if not block.attachment:
            return False
        mime = (block.attachment.mime_type or "").lower()
        return (
            mime.startswith("text/") or
            mime == "application/json" or
            mime.endswith("+json") or
            mime.endswith("+xml")
        )

    def _read_attachment_text(self, attachment: AttachmentRef) -> Optional[str]:
        data_bytes = self._read_attachment_bytes(attachment)
        return self._bytes_to_text(data_bytes)

    def _general_parts_to_function_response_parts(self, parts: List[genai_types.Part]) -> List[genai_types.FunctionResponsePart]:
        function_response_parts: List[genai_types.FunctionResponsePart] = []
        for part in parts:
            if part.inline_data:
                # Convert inline_data (bytes) to base64 data URI and use from_uri
                function_response_parts.append(
                    genai_types.FunctionResponsePart.from_bytes(data=part.inline_data.data, mime_type=part.inline_data.mime_type or "application/octet-stream")
                )
            if part.file_data:
                function_response_parts.append(
                    genai_types.FunctionResponsePart.from_uri(file_uri=part.file_data.file_uri, mime_type=part.file_data.mime_type or "application/octet-stream")
                )
        return function_response_parts

    def _build_tool_response_part(self, message: Message) -> genai_types.Part:
        tool_name = message.metadata.get("tool_name") if isinstance(message.metadata, dict) else None
        tool_name = tool_name or message.tool_call_id or "tool"
        payload, block_parts = self._serialize_tool_message_payload(message)
        return genai_types.Part(
            function_response=genai_types.FunctionResponse(
                name=tool_name,
                response=payload,
                parts=block_parts or None,
            )
        )

    def _block_has_attachment(self, block: Any) -> bool:
        return isinstance(block, MessageBlock) and block.attachment is not None

    def _serialize_tool_message_payload(self, message: Message) -> Tuple[Dict[str, Any], List[genai_types.FunctionResponsePart]]:
        content = message.content
        blocks: List[MessageBlock] = []
        if isinstance(content, str):
            stripped = content.strip()
            if stripped:
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    payload = {"result": stripped}
            else:
                payload = {"result": ""}
            return payload, []

        if isinstance(content, list):
            blocks_payload = []
            for block in content:
                if isinstance(block, MessageBlock):
                    blocks_payload.append(block.to_dict())
                    blocks.append(block)
                elif isinstance(block, dict):
                    blocks_payload.append(block)
                    try:
                        blocks.append(MessageBlock.from_dict(block))
                    except Exception:
                        continue
            parts = self._blocks_to_function_parts(blocks)
            return {"blocks": blocks_payload, "result": message.text_content()}, parts

        parts = self._blocks_to_function_parts(blocks)
        return {"result": message.text_content()}, parts

    def _describe_block(self, block: Any) -> str:
        if isinstance(block, MessageBlock):
            return block.describe()
        if isinstance(block, dict):
            text = block.get("text")
            if text:
                return str(text)
        return str(block)

    def _block_to_parts(self, block: MessageBlock) -> List[genai_types.Part]:
        if block.type is MessageBlockType.TEXT:
            return [genai_types.Part(text=block.text or "")]

        if block.type is MessageBlockType.FILE:
            csv_text = self._maybe_inline_large_csv(block)
            if csv_text is not None:
                return [genai_types.Part(text=csv_text)]

        if block.type in (
            MessageBlockType.IMAGE,
            MessageBlockType.AUDIO,
            MessageBlockType.VIDEO,
            MessageBlockType.FILE,
        ):
            media_part = self._attachment_block_to_part(block)
            return [media_part] if media_part else []

        if block.type is MessageBlockType.DATA:
            data_payload = block.data or {}
            text = block.text or json.dumps(data_payload, ensure_ascii=False)
            return [genai_types.Part(text=text)]

        return []

    def _maybe_inline_large_csv(self, block: MessageBlock) -> Optional[str]:
        """Convert large CSV attachments to inline text to avoid Gemini upload size limits."""

        attachment = block.attachment
        if not attachment:
            return None

        mime = (attachment.mime_type or "").lower()
        name = (attachment.name or "").lower()
        if "text/csv" not in mime and not name.endswith(".csv"):
            return None
        if attachment.remote_file_id:
            return None

        threshold = getattr(
            self,
            "csv_inline_size_threshold_bytes",
            self.CSV_INLINE_SIZE_THRESHOLD_BYTES,
        )

        size_bytes = attachment.size
        data_bytes: Optional[bytes] = None
        if size_bytes is None:
            data_bytes = self._read_attachment_bytes(attachment)
            if data_bytes is None:
                return None
            size_bytes = len(data_bytes)

        if size_bytes is None or size_bytes <= threshold:
            return None

        if data_bytes is None:
            data_bytes = self._read_attachment_bytes(attachment)
            if data_bytes is None:
                return None

        text = self._bytes_to_text(data_bytes)
        if text is None:
            return None

        char_limit = getattr(self, "csv_inline_char_limit", self.CSV_INLINE_CHAR_LIMIT)
        truncated = False
        if len(text) > char_limit:
            text = text[:char_limit]
            truncated = True

        display_name = attachment.name or attachment.attachment_id or "attachment.csv"
        suffix = f"\n\n[truncated after {char_limit} characters]" if truncated else ""
        return f"CSV file '{display_name}' (converted from >3MB upload):\n{text}{suffix}"

    def _bytes_to_text(self, data_bytes: Optional[bytes]) -> Optional[str]:
        if data_bytes is None:
            return None
        try:
            return data_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return data_bytes.decode("utf-8", errors="replace")

    def _attachment_block_to_part(self, block: MessageBlock) -> Optional[genai_types.Part]:
        attachment = block.attachment
        if not attachment:
            return None

        metadata = attachment.metadata or {}
        gemini_file_uri = metadata.get("gemini_file_uri") or attachment.remote_file_id
        mime_type = attachment.mime_type or self._guess_mime_from_block(block)

        if gemini_file_uri:
            return genai_types.Part(
                file_data=genai_types.FileData(
                    file_uri=gemini_file_uri,
                    mime_type=mime_type,
                    # display_name=attachment.name
                )
            )

        blob_data = self._read_attachment_bytes(attachment)
        if blob_data is None:
            return None

        return genai_types.Part(
            inline_data=genai_types.Blob(
                mime_type=mime_type or "application/octet-stream",
                data=blob_data,
                # display_name=attachment.name,
            )
        )

    def _blocks_to_function_parts(
        self,
        blocks: Optional[Sequence[Any]],
    ) -> List[genai_types.FunctionResponsePart]:
        if not blocks:
            return []
        parts: List[genai_types.FunctionResponsePart] = []
        for block in blocks:
            if not isinstance(block, MessageBlock):
                if isinstance(block, dict):
                    try:
                        block = MessageBlock.from_dict(block)
                    except Exception:
                        continue
                else:
                    continue
            attachment = block.attachment
            if not attachment:
                continue
            mime_type = attachment.mime_type or self._guess_mime_from_block(block)
            file_uri = (attachment.metadata or {}).get("gemini_file_uri") or attachment.remote_file_id
            if file_uri:
                parts.append(
                    genai_types.FunctionResponsePart(
                        file_data=genai_types.FunctionResponseFileData(
                            file_uri=file_uri,
                            mime_type=mime_type,
                            display_name=attachment.name,
                        )
                    )
                )
                continue
            data_bytes = self._read_attachment_bytes(attachment)
            if not data_bytes:
                continue
            parts.append(
                genai_types.FunctionResponsePart(
                    inline_data=genai_types.FunctionResponseBlob(
                        mime_type=mime_type or "application/octet-stream",
                        data=data_bytes,
                        display_name=attachment.name,
                    )
                )
            )
        return parts

    def _coerce_message_blocks(self, payload: Any) -> List[MessageBlock]:
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
            return []
        blocks: List[MessageBlock] = []
        for item in payload:
            if isinstance(item, MessageBlock):
                blocks.append(item)
            elif isinstance(item, dict):
                try:
                    blocks.append(MessageBlock.from_dict(item))
                except Exception:
                    continue
        return blocks

    def _encode_thought_signature(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        try:
            return str(value)
        except Exception:
            return None

    def _read_attachment_bytes(self, attachment: AttachmentRef) -> Optional[bytes]:
        if attachment.data_uri:
            decoded = self._decode_data_uri(attachment.data_uri)
            if decoded is not None:
                return decoded
        if attachment.local_path and os.path.exists(attachment.local_path):
            try:
                with open(attachment.local_path, "rb") as handle:
                    return handle.read()
            except OSError:
                return None
        return None

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
        return data.encode("utf-8")

    def _guess_mime_from_block(self, block: MessageBlock) -> str:
        if block.attachment and block.attachment.mime_type:
            return block.attachment.mime_type
        if block.type is MessageBlockType.IMAGE:
            return "image/png"
        if block.type is MessageBlockType.AUDIO:
            return "audio/mpeg"
        if block.type is MessageBlockType.VIDEO:
            return "video/mp4"
        return "application/octet-stream"

    def _map_role(self, role: MessageRole) -> str:
        if role is MessageRole.USER:
            return "user"
        if role is MessageRole.ASSISTANT:
            return "model"
        if role is MessageRole.TOOL:
            return "tool"
        return "user"

    # ---------------------------------------------------------------------
    # Config builders
    # ---------------------------------------------------------------------

    def _build_generation_config(
        self,
        system_instruction: Optional[str],
        tool_specs: Optional[List[ToolSpec]],
        call_params: Dict[str, Any],
    ) -> genai_types.GenerateContentConfig:
        params = dict(self.params or {})
        params.update(call_params)

        config_kwargs: Dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        for key in (
            "temperature",
            "top_p",
            "top_k",
            "candidate_count",
            "max_output_tokens",
            "response_modalities",
            "stop_sequences",
            "seed",
            "presence_penalty",
            "frequency_penalty",
        ):
            if key in params:
                config_kwargs[key] = params.pop(key)

        safety_settings = params.pop("safety_settings", None)
        if safety_settings:
            config_kwargs["safety_settings"] = safety_settings

        image_config = params.pop("image_config", None)
        aspect_ratio = params.pop("aspect_ratio", None)
        if aspect_ratio:
            if image_config is None:
                image_config = {"aspect_ratio": aspect_ratio}
            elif isinstance(image_config, dict):
                image_config = dict(image_config)
                image_config.setdefault("aspect_ratio", aspect_ratio)
            elif isinstance(image_config, genai_types.ImageConfig):
                try:
                    image_config.aspect_ratio = aspect_ratio
                except Exception:
                    image_config = {"aspect_ratio": aspect_ratio}
            else:
                image_config = {"aspect_ratio": aspect_ratio}
        if image_config:
            config_kwargs["image_config"] = self._coerce_image_config(image_config)

        audio_config = params.pop("audio_config", None)
        if audio_config:
            config_kwargs["audio_config"] = audio_config

        video_config = params.pop("video_config", None)
        if video_config:
            config_kwargs["video_config"] = video_config

        tools = self._build_tools(tool_specs or [])
        if tools:
            config_kwargs["tools"] = tools

        tool_config_payload = params.pop("tool_config", None)
        function_calling_payload = params.pop("function_calling_config", None)
        if function_calling_payload:
            tool_config_payload = tool_config_payload or {}
            tool_config_payload["function_calling_config"] = function_calling_payload

        if tool_config_payload:
            config_kwargs["tool_config"] = self._coerce_tool_config(tool_config_payload)

        automatic_fn_calling = params.pop("automatic_function_calling", None)
        if automatic_fn_calling:
            config_kwargs["automatic_function_calling"] = self._coerce_automatic_function_calling(
                automatic_fn_calling
            )

        return genai_types.GenerateContentConfig(**config_kwargs)

    def _build_http_options(self, base_url: str) -> Optional[genai_types.HttpOptions]:
        if not base_url:
            return None
        try:
            return genai_types.HttpOptions(base_url=base_url, timeout=4 * 60 * 1000)  # 4 min
        except Exception:
            return None

    def _coerce_image_config(self, image_config: Any) -> Any:
        if isinstance(image_config, genai_types.ImageConfig):
            return image_config
        if isinstance(image_config, dict):
            try:
                return genai_types.ImageConfig(**image_config)
            except Exception:
                return image_config
        return image_config

    def _build_tools(self, tool_specs: List[ToolSpec]) -> List[genai_types.Tool]:
        if not tool_specs:
            return []

        declarations = []
        for spec in tool_specs:
            fn_payload = spec.to_gemini_function()
            parameters = fn_payload.get("parameters") or {"type": "object", "properties": {}}
            if 'title' in parameters:
                parameters.pop('title')
            # Replace 'title' with 'description' in properties
            for prop_name, prop_value in parameters.get('properties', {}).items():
                if isinstance(prop_value, dict) and 'title' in prop_value:
                    prop_value['description'] = prop_value.pop('title')
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=fn_payload.get("name", ""),
                    description=fn_payload.get("description") or "",
                    parameters=parameters,
                )
            )
        return [genai_types.Tool(function_declarations=declarations)]

    def _coerce_tool_config(self, payload: Any) -> genai_types.ToolConfig:
        if isinstance(payload, genai_types.ToolConfig):
            return payload
        kwargs: Dict[str, Any] = {}
        if isinstance(payload, dict):
            fn_payload = payload.get("function_calling_config")
            if fn_payload:
                kwargs["function_calling_config"] = self._coerce_function_calling_config(fn_payload)
        return genai_types.ToolConfig(**kwargs)

    def _coerce_function_calling_config(self, payload: Any) -> genai_types.FunctionCallingConfig:
        if isinstance(payload, genai_types.FunctionCallingConfig):
            return payload
        if isinstance(payload, str):
            return genai_types.FunctionCallingConfig(mode=payload)
        if isinstance(payload, dict):
            return genai_types.FunctionCallingConfig(**payload)
        raise ValueError("Invalid function calling configuration payload")

    def _coerce_automatic_function_calling(self, payload: Any) -> Any:
        config_cls = getattr(genai_types, "AutomaticFunctionCallingConfig", None)
        if config_cls is None:
            raise ValueError("Automatic function calling config not supported in current SDK version")
        if isinstance(payload, config_cls):
            return payload
        if isinstance(payload, dict):
            return config_cls(**payload)
        raise ValueError("Invalid automatic function calling config payload")

    # ---------------------------------------------------------------------
    # Response parsing
    # ---------------------------------------------------------------------

    def _deserialize_response(self, response: Any) -> Message:
        candidate = self._select_primary_candidate(response)
        if not candidate:
            return Message(role=MessageRole.ASSISTANT, content="")

        content = getattr(candidate, "content", None)
        if not content:
            return Message(role=MessageRole.ASSISTANT, content=response.text if hasattr(response, "text") else "")

        blocks, tool_calls = self._parse_candidate_parts(getattr(content, "parts", []) or [])
        if not blocks:
            fallback = getattr(response, "text", None) or ""
            blocks = [MessageBlock(MessageBlockType.TEXT, text=fallback)] if fallback else []

        return Message(
            role=MessageRole.ASSISTANT,
            content=blocks or "",
            tool_calls=tool_calls,
        )

    def _select_primary_candidate(self, response: Any) -> Any:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None
        return candidates[0]

    def _parse_candidate_parts(
        self,
        parts: Sequence[Any],
    ) -> Tuple[List[MessageBlock], List[ToolCallPayload]]:
        blocks: List[MessageBlock] = []
        tool_calls: List[ToolCallPayload] = []

        for part in parts:
            if hasattr(part, "text") and part.text is not None:
                blocks.append(MessageBlock(MessageBlockType.TEXT, text=part.text))
                continue

            function_call = getattr(part, "function_call", None)
            if function_call:
                thought_signature = getattr(part, "thought_signature", None)
                tool_calls.append(
                    self._build_tool_call_payload(function_call, thought_signature=thought_signature)
                )
                continue

            inline_data = getattr(part, "inline_data", None)
            if inline_data:
                blocks.append(self._build_inline_block(inline_data))
                continue

            file_data = getattr(part, "file_data", None)
            if file_data:
                blocks.append(self._build_file_block(file_data))
                continue

            function_response = getattr(part, "function_response", None)
            if function_response:
                blocks.append(
                    MessageBlock(
                        type=MessageBlockType.DATA,
                        text=json.dumps(function_response.response or {}, ensure_ascii=False),
                        data={
                            "function_name": getattr(function_response, "name", ""),
                            "response": function_response.response or {},
                        },
                    )
                )
                continue

        return blocks, tool_calls

    def _build_tool_call_payload(self, fn_call: Any, *, thought_signature: Any = None) -> ToolCallPayload:
        call_id = getattr(fn_call, "name", "") or uuid.uuid4().hex
        arguments = getattr(fn_call, "args", {}) or {}
        try:
            arg_str = json.dumps(arguments, ensure_ascii=False)
        except (TypeError, ValueError):
            arg_str = str(arguments)
        metadata: Dict[str, Any] = {}
        encoded_signature = self._encode_thought_signature(thought_signature)
        if encoded_signature:
            metadata["gemini_thought_signature_b64"] = encoded_signature
        return ToolCallPayload(
            id=call_id,
            function_name=getattr(fn_call, "name", "") or call_id,
            arguments=arg_str,
            type="function",
            metadata=metadata,
        )

    def _build_inline_block(self, blob: Any) -> MessageBlock:
        mime_type = getattr(blob, "mime_type", "") or "application/octet-stream"
        data_bytes = getattr(blob, "data", None) or b""
        data_uri = self._encode_data_uri(mime_type, data_bytes)
        block_type = self._block_type_from_mime(mime_type)
        return MessageBlock(
            type=block_type,
            attachment=AttachmentRef(
                attachment_id=uuid.uuid4().hex,
                mime_type=mime_type,
                data_uri=data_uri,
                metadata={"source": "gemini_inline"},
            ),
        )

    def _build_file_block(self, file_data: Any) -> MessageBlock:
        mime_type = getattr(file_data, "mime_type", None)
        file_uri = getattr(file_data, "file_uri", None) or getattr(file_data, "file", None)
        block_type = self._block_type_from_mime(mime_type or "")
        return MessageBlock(
            type=block_type,
            attachment=AttachmentRef(
                attachment_id=uuid.uuid4().hex,
                mime_type=mime_type,
                remote_file_id=file_uri,
                metadata={"gemini_file_uri": file_uri, "source": "gemini_file"},
            ),
        )

    def _block_type_from_mime(self, mime_type: str) -> MessageBlockType:
        if mime_type.startswith("image/"):
            return MessageBlockType.IMAGE
        if mime_type.startswith("audio/"):
            return MessageBlockType.AUDIO
        if mime_type.startswith("video/"):
            return MessageBlockType.VIDEO
        return MessageBlockType.FILE

    def _encode_data_uri(self, mime_type: str, data: bytes) -> str:
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    # ---------------------------------------------------------------------
    # Token tracking
    # ---------------------------------------------------------------------

    def _track_token_usage(self, response: Any) -> None:
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
        usage.provider = "gemini"

        token_tracker.record_usage(node_id, self.model_name, usage, provider="gemini")
