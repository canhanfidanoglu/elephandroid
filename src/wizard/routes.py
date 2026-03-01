"""Project Wizard routes — multi-source task aggregation and project creation."""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.database import get_db
from src.planner.client import create_plan, set_plan_categories
from src.sync.engine import EPIC_CATEGORY_MAP, sync_tasks_to_planner

from .aggregator import merge_sources
from .collector import (
    collect_from_email,
    collect_from_teams_chat,
    collect_from_text,
    collect_from_transcript,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard", tags=["wizard"])


# --- Request Models ---


class TextSource(BaseModel):
    text: str
    context: str | None = None


class EmailSource(BaseModel):
    message_id: str


class TeamsChatSource(BaseModel):
    chat_id: str


class TranscriptSource(BaseModel):
    join_url: str
    meeting_subject: str | None = None


class WizardRequest(BaseModel):
    """Multi-source project creation request."""
    texts: list[TextSource] = []
    emails: list[EmailSource] = []
    teams_chats: list[TeamsChatSource] = []
    transcripts: list[TranscriptSource] = []
    ticket_prefix: str = "PRJ"


class CreateProjectRequest(BaseModel):
    """Final project creation after review."""
    group_id: str
    plan_title: str
    tasks_json: str  # JSON-serialized list of ParsedTask dicts
    auto_create_buckets: bool = True


# --- Endpoints ---


@router.post("/extract")
async def extract_from_sources(
    body: WizardRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Extract tasks from all provided sources, deduplicate, and return for review.

    This is step 1 — the user reviews the merged task list before creating the project.
    """
    sources = []
    errors = []

    # Texts
    for src in body.texts:
        try:
            sources.append(await collect_from_text(src.text, src.context, body.ticket_prefix))
        except Exception as exc:
            errors.append({"source": "text", "error": str(exc)})

    # Emails
    for src in body.emails:
        try:
            sources.append(await collect_from_email(user.access_token, src.message_id, body.ticket_prefix))
        except Exception as exc:
            errors.append({"source": f"email:{src.message_id}", "error": str(exc)})

    # Teams chats
    for src in body.teams_chats:
        try:
            sources.append(await collect_from_teams_chat(user.access_token, src.chat_id, body.ticket_prefix))
        except Exception as exc:
            errors.append({"source": f"chat:{src.chat_id}", "error": str(exc)})

    # Transcripts
    for src in body.transcripts:
        try:
            sources.append(await collect_from_transcript(
                user.access_token, src.join_url, src.meeting_subject, body.ticket_prefix
            ))
        except Exception as exc:
            errors.append({"source": f"transcript:{src.join_url[:30]}", "error": str(exc)})

    if not sources:
        raise HTTPException(status_code=400, detail="No sources provided or all sources failed.")

    # Merge and deduplicate
    merged_tasks = merge_sources(sources, prefix=body.ticket_prefix)

    # Build source summary
    source_summary = [
        {"label": label, "task_count": len(tasks)}
        for label, tasks in sources
    ]

    return {
        "tasks": [t.model_dump(mode="json") for t in merged_tasks],
        "task_count": len(merged_tasks),
        "sources": source_summary,
        "errors": errors,
    }


@router.post("/extract-document")
async def extract_from_document_upload(
    file: UploadFile,
    ticket_prefix: str = Form("PRJ"),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Extract tasks from an uploaded document (for adding to wizard sources)."""
    from .collector import collect_from_document

    file_bytes = await file.read()
    filename = file.filename or "upload.txt"

    try:
        label, tasks = await collect_from_document(filename, file_bytes, ticket_prefix)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to extract from document: {exc}")

    return {
        "source": label,
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "task_count": len(tasks),
    }


@router.post("/create-project")
async def create_project(
    body: CreateProjectRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Create a Planner plan with all tasks from the wizard.

    This is step 2 — after the user reviews and confirms the task list.
    """
    import json
    from src.excel.models import ParsedTask

    # Parse tasks
    try:
        raw_list = json.loads(body.tasks_json)
        tasks = [ParsedTask(**t) for t in raw_list]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid tasks JSON: {exc}")

    if not tasks:
        raise HTTPException(status_code=400, detail="No tasks to create.")

    # Create plan
    plan = await create_plan(user.access_token, body.group_id, body.plan_title)

    # Set category labels
    category_labels = {v: k.title() for k, v in EPIC_CATEGORY_MAP.items()}
    try:
        await set_plan_categories(user.access_token, plan.id, category_labels)
    except Exception:
        pass  # non-critical

    # Sync all tasks
    sync_result = await sync_tasks_to_planner(
        access_token=user.access_token,
        tasks=tasks,
        plan_id=plan.id,
        default_bucket_id="",
        auto_create_buckets=body.auto_create_buckets,
    )

    return {
        "plan_id": plan.id,
        "plan_title": body.plan_title,
        "sync": sync_result.to_dict(),
        "task_count": len(tasks),
    }
