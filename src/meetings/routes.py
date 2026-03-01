import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.chat.engine import approve_tasks
from src.chat.models import ChatMessage, ChatSession, PendingTaskSet
from src.database import get_db
from src.sync.engine import sync_tasks_to_planner

from .client import get_transcript_content, list_calendar_teams_meetings
from .summarizer import summarize_transcript

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("/recent")
async def list_recent_meetings(
    after: str | None = Query(None, description="ISO date, e.g. 2026-01-01T00:00:00Z"),
    before: str | None = Query(None, description="ISO date"),
    limit: int = Query(20, ge=1, le=50),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    return await list_calendar_teams_meetings(
        user.access_token, after=after, before=before, limit=limit
    )


@router.get("/transcript")
async def get_transcript(
    join_url: str = Query(..., description="Teams meeting join URL"),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    try:
        result = await get_transcript_content(user.access_token, join_url)
        return {"content": result["content"], "transcript_id": result["transcript_id"]}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class SummarizeRequest(BaseModel):
    join_url: str
    meeting_subject: str | None = None
    ticket_prefix: str = "MTG"


@router.post("/summarize")
async def summarize_meeting(
    body: SummarizeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Fetch transcript and summarize with task extraction."""
    try:
        transcript = await get_transcript_content(user.access_token, body.join_url)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    result = await summarize_transcript(
        transcript["content"],
        meeting_subject=body.meeting_subject,
        ticket_prefix=body.ticket_prefix,
    )

    return {
        "summary": result["summary"],
        "key_decisions": result["key_decisions"],
        "action_items": result["action_items"],
        "tasks": [t.model_dump(mode="json") for t in result["tasks"]],
        "task_count": len(result["tasks"]),
    }


class SyncMeetingTasksRequest(BaseModel):
    join_url: str
    meeting_subject: str | None = None
    ticket_prefix: str = "MTG"
    plan_id: str
    default_bucket_id: str
    auto_create_buckets: bool = True


@router.post("/summarize-and-sync")
async def summarize_and_sync(
    body: SyncMeetingTasksRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Fetch transcript, summarize, extract tasks, and sync to Planner."""
    try:
        transcript = await get_transcript_content(user.access_token, body.join_url)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    result = await summarize_transcript(
        transcript["content"],
        meeting_subject=body.meeting_subject,
        ticket_prefix=body.ticket_prefix,
    )

    sync_result = None
    if result["tasks"]:
        sr = await sync_tasks_to_planner(
            access_token=user.access_token,
            tasks=result["tasks"],
            plan_id=body.plan_id,
            default_bucket_id=body.default_bucket_id,
            auto_create_buckets=body.auto_create_buckets,
        )
        sync_result = sr.to_dict()

    return {
        "summary": result["summary"],
        "key_decisions": result["key_decisions"],
        "action_items": result["action_items"],
        "tasks": [t.model_dump(mode="json") for t in result["tasks"]],
        "sync": sync_result,
    }
