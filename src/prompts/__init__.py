"""Centralized prompt management.

All LLM prompts live here, organized by domain.
Import from this package instead of module-local prompt files.
"""

from .chat import CHAT_SYSTEM, EXTRACTION_TRIGGER
from .extraction import TASK_EXTRACTION_SYSTEM, build_user_prompt
from .meeting import MEETING_SUMMARY_SYSTEM, MEETING_TRANSCRIPT_CONTEXT
from .reports import NL_REPORT_SYSTEM
