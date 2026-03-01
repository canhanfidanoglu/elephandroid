"""Summarize meeting transcripts and extract tasks using the LLM provider."""

import logging

from src.ai.task_extractor import _parse_task_item
from src.excel.models import ParsedTask
from src.prompts import MEETING_SUMMARY_SYSTEM
from src.providers import generate_json

logger = logging.getLogger(__name__)


async def summarize_transcript(
    transcript_text: str,
    meeting_subject: str | None = None,
    ticket_prefix: str = "MTG",
) -> dict:
    """Summarize a meeting transcript and extract tasks.

    Returns: {summary, key_decisions, action_items, tasks: list[ParsedTask]}
    """
    from datetime import date as _date

    context_parts = [f"Current date: {_date.today().isoformat()}"]
    if meeting_subject:
        context_parts.append(f"Meeting subject: {meeting_subject}")
    context_parts.append(f"Ticket prefix: {ticket_prefix}")
    context_parts.append(
        f"--- TRANSCRIPT START ---\n{transcript_text}\n--- TRANSCRIPT END ---"
    )
    user_prompt = "\n".join(context_parts)

    raw = await generate_json(MEETING_SUMMARY_SYSTEM, user_prompt)

    # Parse tasks
    tasks: list[ParsedTask] = []
    for idx, item in enumerate(raw.get("tasks", []), start=1):
        try:
            task = _parse_task_item(item, idx, ticket_prefix)
            tasks.append(task)
        except Exception as exc:
            logger.warning("Skipping malformed meeting task %d: %s", idx, exc)

    return {
        "summary": raw.get("summary", ""),
        "key_decisions": raw.get("key_decisions", []),
        "action_items": raw.get("action_items", []),
        "tasks": tasks,
    }
