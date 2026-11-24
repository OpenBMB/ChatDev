from collections.abc import Mapping
from typing import Any


def call_user(instruction: str, _context: dict | None = None) -> str:
    """
    If you think it's necessary to get input from the user, use this function to send the instruction to the user and get their response.

    Args:
        instruction: The instruction to send to the user.
        _context: Optional runtime context dictionary containing human_prompt service and node configuration.

    Returns:
        str: User response text or fallback notification if human prompt is unavailable.
    """
    if not isinstance(instruction, str):
        raise TypeError(
            f"instruction must be a string, got {type(instruction).__name__}"
        )

    stripped_instruction = instruction.strip()
    if not stripped_instruction:
        raise ValueError("instruction cannot be empty")

    ctx = _context if isinstance(_context, Mapping) else {}
    prompt = ctx.get("human_prompt")

    if prompt is None or not hasattr(prompt, "request") or not callable(prompt.request):
        return f"Human prompt unavailable, default response for instruction: {stripped_instruction}"

    node_id_val = ctx.get("node_id")
    node_id = (
        str(node_id_val).strip()
        if node_id_val is not None and str(node_id_val).strip()
        else "model_function_calling"
    )

    task_desc_val = ctx.get("task_description")
    task_desc = (
        str(task_desc_val).strip()
        if task_desc_val is not None and str(task_desc_val).strip()
        else "Please respond to the model instruction."
    )

    raw_meta = ctx.get("metadata")
    metadata: dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, Mapping) else {}
    metadata.setdefault("source", "function_tool")

    result = prompt.request(
        node_id=node_id,
        task_description=task_desc,
        inputs=stripped_instruction,
        metadata=metadata,
    )

    if hasattr(result, "text"):
        return result.text or ""
    return str(result) if result is not None else ""
