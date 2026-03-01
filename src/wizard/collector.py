"""Collect tasks from various sources — text, documents, emails, chats, transcripts."""

import logging

from src.ai.task_extractor import extract_from_document, extract_from_text
from src.emails.client import get_message_body
from src.excel.models import ParsedTask
from src.meetings.client import get_transcript_content
from src.meetings.summarizer import summarize_transcript
from src.teams_chat.client import format_chat_to_text, get_chat_messages

logger = logging.getLogger(__name__)


async def collect_from_text(
    text: str,
    context: str | None = None,
    prefix: str = "PRJ",
) -> tuple[str, list[ParsedTask]]:
    """Extract tasks from free-form text."""
    result = await extract_from_text(text, context=context, ticket_prefix=prefix)
    return ("Free text", result.tasks)


async def collect_from_document(
    filename: str,
    file_bytes: bytes,
    prefix: str = "PRJ",
) -> tuple[str, list[ParsedTask]]:
    """Extract tasks from an uploaded document."""
    result = await extract_from_document(filename, file_bytes, ticket_prefix=prefix)
    return (f"Document: {filename}", result.tasks)


async def collect_from_email(
    access_token: str,
    message_id: str,
    prefix: str = "PRJ",
) -> tuple[str, list[ParsedTask]]:
    """Extract tasks from an Outlook email."""
    msg = await get_message_body(access_token, message_id)
    text = f"From: {msg['from_name']} <{msg['from_email']}>\nSubject: {msg['subject']}\n\n{msg['body_text']}"
    result = await extract_from_text(text, context=f"Email: {msg['subject']}", ticket_prefix=prefix)
    label = f"Email: {msg['subject'][:50]}"
    return (label, result.tasks)


async def collect_from_teams_chat(
    access_token: str,
    chat_id: str,
    prefix: str = "PRJ",
) -> tuple[str, list[ParsedTask]]:
    """Extract tasks from a Teams chat conversation."""
    messages = await get_chat_messages(access_token, chat_id)
    if not messages:
        return ("Teams chat", [])
    text = format_chat_to_text(messages)
    result = await extract_from_text(text, context="Teams chat conversation", ticket_prefix=prefix)
    return ("Teams chat", result.tasks)


async def collect_from_transcript(
    access_token: str,
    join_url: str,
    meeting_subject: str | None = None,
    prefix: str = "PRJ",
) -> tuple[str, list[ParsedTask]]:
    """Extract tasks from a Teams meeting transcript."""
    transcript = await get_transcript_content(access_token, join_url)
    result = await summarize_transcript(
        transcript["content"],
        meeting_subject=meeting_subject,
        ticket_prefix=prefix,
    )
    label = f"Meeting: {meeting_subject or 'Unknown'}"
    return (label, result["tasks"])
