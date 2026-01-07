def call_user(instruction: str, _context: dict | None = None) -> str:
    """
    If you think it's necessary to get input from the user, use this function to send the instruction to the user and get their response.

    Args:
        instruction: The instruction to send to the user.
    """
    prompt = _context.get("human_prompt") if _context else None
    if prompt is None:
        return f"Human prompt unavailable, default response for instruction: {instruction}"
    result = prompt.request(
        node_id=_context.get("node_id", "model_function_calling"),
        task_description="Please response to the model instruction.",
        inputs=instruction,
        metadata={"source": "function_tool"},
    )
    return result.text
