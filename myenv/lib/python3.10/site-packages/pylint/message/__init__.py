# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""All the classes related to Message handling."""

from pylint.message.message import Message
from pylint.message.message_definition import MessageDefinition
from pylint.message.message_definition_store import MessageDefinitionStore
from pylint.message.message_id_store import MessageIdStore

__all__ = [
    "Message",
    "MessageDefinition",
    "MessageDefinitionStore",
    "MessageIdStore",
]
