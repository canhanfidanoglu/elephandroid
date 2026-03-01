import logging
from datetime import date

from src.excel.models import ParsedTask

from .document_parser import parse_document
from .models import ExtractionResult
from src.providers import generate_json
from src.prompts import TASK_EXTRACTION_SYSTEM, build_user_prompt

logger = logging.getLogger(__name__)


async def extract_from_text(
    text: str,
    context: str | None = None,
    ticket_prefix: str = "AI",
) -> ExtractionResult:
    """Send text to the SLM and return structured tasks."""
    user_prompt = build_user_prompt(text, context, ticket_prefix)
    raw = await generate_json(TASK_EXTRACTION_SYSTEM, user_prompt)

    plan_name = raw.get("plan_name")
    tasks: list[ParsedTask] = []

    for idx, item in enumerate(raw.get("tasks", []), start=1):
        try:
            task = _parse_task_item(item, idx, ticket_prefix)
            tasks.append(task)
        except Exception as exc:
            logger.warning("Skipping malformed task at index %d: %s", idx, exc)

    return ExtractionResult(plan_name=plan_name, tasks=tasks)


async def extract_from_document(
    filename: str,
    file_bytes: bytes,
    context: str | None = None,
    ticket_prefix: str = "AI",
) -> ExtractionResult:
    """Parse a document file, then extract tasks via the SLM."""
    text = parse_document(filename, file_bytes)
    return await extract_from_text(text, context=context, ticket_prefix=ticket_prefix)


def _parse_task_item(item: dict, idx: int, prefix: str) -> ParsedTask:
    """Defensively parse a single task dict from SLM output."""
    # Enforce ticket ID format
    ticket_id = item.get("ticket_id", "")
    if not ticket_id or not ticket_id.upper().startswith(prefix.upper()):
        ticket_id = f"{prefix}-{idx:03d}"

    title = str(item.get("title", "Untitled Task"))

    epic = item.get("epic") or None
    description = item.get("description") or None
    bucket_name = item.get("bucket_name") or None
    raw_assignee = item.get("assignee")
    if isinstance(raw_assignee, list):
        assignee = ", ".join(str(a) for a in raw_assignee) or None
    else:
        assignee = str(raw_assignee) if raw_assignee else None

    # Priority
    priority = _safe_int(item.get("priority"), default=5)
    if priority not in (1, 3, 5, 9):
        priority = 5

    # Dates
    start_date = _safe_date(item.get("start_date"))
    due_date = _safe_date(item.get("due_date"))

    # Checklist
    raw_checklist = item.get("checklist_items", [])
    checklist_items = [str(c) for c in raw_checklist if c]

    return ParsedTask(
        ticket_id=ticket_id,
        title=title,
        epic=epic,
        description=description,
        bucket_name=bucket_name,
        priority=priority,
        start_date=start_date,
        due_date=due_date,
        assignee=assignee,
        checklist_items=checklist_items,
    )


def _safe_int(value, default: int = 5) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
