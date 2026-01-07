"""Helpers for building initial task inputs with optional attachments."""

import mimetypes
from pathlib import Path
from typing import List, Sequence, Union

from entity.messages import Message, MessageBlock, MessageBlockType, MessageRole
from utils.attachments import AttachmentStore


class TaskInputBuilder:
    """Builds task input payloads that optionally include attachments."""

    def __init__(self, attachment_store: AttachmentStore):
        self.attachment_store = attachment_store

    def build_from_file_paths(
        self,
        prompt: str,
        attachment_paths: Sequence[str],
    ) -> Union[str, List[Message]]:
        if not attachment_paths:
            return prompt

        blocks: List[MessageBlock] = []

        for raw_path in attachment_paths:
            file_path = Path(raw_path).expanduser()
            if not file_path.exists():
                raise FileNotFoundError(f"Attachment not found: {file_path}")
            mime_type, _ = mimetypes.guess_type(str(file_path))
            record = self.attachment_store.register_file(
                file_path,
                kind=MessageBlockType.from_mime_type(mime_type),
                display_name=file_path.name,
                mime_type=mime_type,
                extra={
                    "source": "user_upload",
                    "origin": "cli_attachment",
                    "original_path": str(file_path),
                },
            )
            blocks.append(record.as_message_block())

        return self.build_from_blocks(prompt, blocks)

    @staticmethod
    def build_from_blocks(prompt: str, blocks: Sequence[MessageBlock]) -> List[Message]:
        final_blocks: List[MessageBlock] = []
        if prompt:
            final_blocks.append(MessageBlock.text_block(prompt))
        final_blocks.extend(blocks)
        if not final_blocks:
            final_blocks.append(MessageBlock.text_block(""))
        return [
            Message(
                role=MessageRole.USER,
                content=final_blocks,
                metadata={"source": "TASK"},
            )
        ]
