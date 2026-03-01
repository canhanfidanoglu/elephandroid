"""Teams chat routes — chat listing, message retrieval, task extraction, and Planner sync."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.ai.task_extractor import extract_from_text
from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.sync.engine import sync_tasks_to_planner

from .client import (
    filter_chats_by_topic,
    format_chat_to_text,
    get_chat_attachments,
    get_chat_messages,
    list_chats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams-chat", tags=["teams-chat"])


class ExtractAndSyncRequest(BaseModel):
    plan_id: str
    default_bucket_id: str
    auto_create_buckets: bool = True
    ticket_prefix: str = "TC"


class BatchExtractRequest(BaseModel):
    chat_ids: list[str]
    ticket_prefix: str = "TC"


@router.get("/chats")
async def chats(
    user: AuthenticatedUser = Depends(get_current_user),
    top: int = Query(20, ge=1, le=50),
    chat_type: str | None = Query(None, description='Filter by chat type: "oneOnOne", "group", or "meeting"'),
    search: str | None = Query(None, description="Filter chats by topic substring (case-insensitive)"),
) -> list[dict]:
    """List the user's recent Teams chats."""
    try:
        result = await list_chats(user.access_token, top=top, chat_type=chat_type)
        if search:
            result = filter_chats_by_topic(result, search)
        return result
    except Exception as exc:
        logger.exception("Failed to list chats")
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/chats/{chat_id}/messages")
async def messages(
    chat_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    top: int = Query(50, ge=1, le=100),
) -> list[dict]:
    """Fetch messages from a specific Teams chat."""
    return await get_chat_messages(user.access_token, chat_id, top=top)


@router.post("/chats/{chat_id}/extract")
async def extract_from_chat(
    chat_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    ticket_prefix: str = Query("TC"),
    include_attachments: bool = Query(False, description="Include attachment info in extraction context"),
) -> dict:
    """Fetch chat messages and extract tasks via SLM."""
    msgs = await get_chat_messages(user.access_token, chat_id)
    if not msgs:
        raise HTTPException(status_code=400, detail="No messages found in this chat.")

    text = format_chat_to_text(msgs)

    if include_attachments:
        attachments = await get_chat_attachments(user.access_token, chat_id)
        if attachments:
            att_lines = [
                f"- {att['name']} (shared by {att['message_from']})"
                for att in attachments
            ]
            text += "\n\n[Attachments shared in this chat]\n" + "\n".join(att_lines)

    context = "Teams chat conversation"
    result = await extract_from_text(text, context=context, ticket_prefix=ticket_prefix)
    return {
        "plan_name": result.plan_name,
        "tasks": [t.model_dump(mode="json") for t in result.tasks],
        "message_count": len(msgs),
    }


@router.post("/chats/{chat_id}/extract-and-sync")
async def extract_and_sync(
    chat_id: str,
    body: ExtractAndSyncRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Fetch chat messages, extract tasks, and sync to Planner."""
    msgs = await get_chat_messages(user.access_token, chat_id)
    if not msgs:
        raise HTTPException(status_code=400, detail="No messages found in this chat.")

    text = format_chat_to_text(msgs)
    context = "Teams chat conversation"
    result = await extract_from_text(text, context=context, ticket_prefix=body.ticket_prefix)

    if not result.tasks:
        raise HTTPException(status_code=400, detail="No tasks extracted from this chat.")

    sync_result = await sync_tasks_to_planner(
        access_token=user.access_token,
        tasks=result.tasks,
        plan_id=body.plan_id,
        default_bucket_id=body.default_bucket_id,
        auto_create_buckets=body.auto_create_buckets,
    )
    return {
        "plan_name": result.plan_name,
        "task_count": len(result.tasks),
        "sync": sync_result.to_dict(),
    }


@router.post("/chats/batch-extract")
async def batch_extract(
    body: BatchExtractRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Extract tasks from multiple chats at once.

    Fetches messages from each chat, combines all text, then runs a single
    extraction pass through the SLM.
    """
    if not body.chat_ids:
        raise HTTPException(status_code=400, detail="chat_ids must not be empty.")

    all_texts: list[str] = []
    total_messages = 0

    for chat_id in body.chat_ids:
        msgs = await get_chat_messages(user.access_token, chat_id)
        if msgs:
            total_messages += len(msgs)
            all_texts.append(format_chat_to_text(msgs))

    if not all_texts:
        raise HTTPException(
            status_code=400, detail="No messages found in any of the provided chats."
        )

    combined_text = "\n\n---\n\n".join(all_texts)
    context = "Teams chat conversations (multiple chats)"
    result = await extract_from_text(
        combined_text, context=context, ticket_prefix=body.ticket_prefix
    )

    return {
        "plan_name": result.plan_name,
        "tasks": [t.model_dump(mode="json") for t in result.tasks],
        "chat_count": len(body.chat_ids),
        "message_count": total_messages,
    }
