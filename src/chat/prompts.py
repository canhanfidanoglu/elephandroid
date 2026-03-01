"""Backward compatibility — prompts moved to src/prompts/."""

from src.prompts import CHAT_SYSTEM as CHAT_SYSTEM_PROMPT
from src.prompts import EXTRACTION_TRIGGER as EXTRACTION_TRIGGER_PROMPT
from src.prompts import MEETING_TRANSCRIPT_CONTEXT

__all__ = [
    "CHAT_SYSTEM_PROMPT",
    "EXTRACTION_TRIGGER_PROMPT",
    "MEETING_TRANSCRIPT_CONTEXT",
]
