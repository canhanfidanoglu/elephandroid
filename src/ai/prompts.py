"""Backward compatibility — prompts moved to src/prompts/."""

from src.prompts import TASK_EXTRACTION_SYSTEM as TASK_EXTRACTION_SYSTEM_PROMPT
from src.prompts import build_user_prompt

__all__ = ["TASK_EXTRACTION_SYSTEM_PROMPT", "build_user_prompt"]
