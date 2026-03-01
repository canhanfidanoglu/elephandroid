"""Backward compatibility — stream_chat delegates to src.providers.

extract_json_action stays here as it is chat-specific logic.
"""

import json
import re

from src.providers import stream_chat

__all__ = ["stream_chat", "extract_json_action"]


def extract_json_action(text: str) -> dict | None:
    """Try to extract a JSON action block from assistant response text.

    Looks for ```json ... ``` fenced blocks or raw JSON with "action" key.
    Returns the parsed dict if found, else None.
    """
    # Try fenced code block first
    pattern = r"```json\s*\n?(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(1))
            if isinstance(obj, dict) and "action" in obj:
                return obj
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object with "action" key
    brace_start = text.find('{"action"')
    if brace_start == -1:
        return None
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[brace_start : i + 1])
                    if isinstance(obj, dict) and "action" in obj:
                        return obj
                except json.JSONDecodeError:
                    pass
                break
    return None
