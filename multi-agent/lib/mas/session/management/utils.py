def derive_title(inputs: dict[str, str], max_chars: int = 40) -> str | None:
    """
    Returns the first non-empty user prompt clipped to `max_chars`.
    """
    prompt = inputs.get("user_prompt") or next(iter(inputs.values()), "")
    prompt = prompt.strip()
    return (prompt[:max_chars] + "…") if len(prompt) > max_chars else (prompt or None)
