"""Outlook email routes — inbox listing, task extraction, and Planner sync."""

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.ai.document_parser import parse_document
from src.ai.task_extractor import extract_from_text
from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.sync.engine import sync_tasks_to_planner

from .client import get_message_attachments, get_message_body, list_inbox_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])


class ExtractAndSyncRequest(BaseModel):
    message_id: str
    plan_id: str
    default_bucket_id: str
    auto_create_buckets: bool = True
    ticket_prefix: str = "EM"


class ExtractTextRequest(BaseModel):
    subject: str = ""
    body: str
    ticket_prefix: str = "EM"


class BatchExtractRequest(BaseModel):
    message_ids: list[str]
    include_attachments: bool = False
    ticket_prefix: str = "EM"


@router.get("/inbox")
async def inbox(
    user: AuthenticatedUser = Depends(get_current_user),
    top: int = Query(20, ge=1, le=50),
    after: str | None = Query(None),
    before: str | None = Query(None),
    search: str | None = Query(None),
) -> list[dict]:
    """List recent inbox messages."""
    try:
        return await list_inbox_messages(
            user.access_token, top=top, after=after, before=before, search=search
        )
    except Exception as exc:
        import traceback
        with open("/tmp/inbox_error.log", "w") as f:
            traceback.print_exc(file=f)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/{message_id}/extract")
async def extract_from_email(
    message_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    ticket_prefix: str = Query("EM"),
) -> dict:
    """Fetch an email's body and extract tasks via SLM."""
    msg = await get_message_body(user.access_token, message_id)
    context = f"Email from: {msg['from_name']} <{msg['from_email']}>, Subject: {msg['subject']}"
    result = await extract_from_text(msg["body_text"], context=context, ticket_prefix=ticket_prefix)
    return {
        "plan_name": result.plan_name,
        "tasks": [t.model_dump(mode="json") for t in result.tasks],
        "source": {"subject": msg["subject"], "from": msg["from_email"]},
    }


@router.post("/extract-and-sync")
async def extract_and_sync(
    body: ExtractAndSyncRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Fetch email, extract tasks, and sync directly to Planner."""
    msg = await get_message_body(user.access_token, body.message_id)
    context = f"Email from: {msg['from_name']} <{msg['from_email']}>, Subject: {msg['subject']}"
    result = await extract_from_text(msg["body_text"], context=context, ticket_prefix=body.ticket_prefix)

    if not result.tasks:
        raise HTTPException(status_code=400, detail="No tasks extracted from this email.")

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


@router.post("/extract-text")
async def extract_from_pasted_text(
    body: ExtractTextRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Extract tasks from pasted email text (Gmail fallback)."""
    context = f"Email subject: {body.subject}" if body.subject else None
    result = await extract_from_text(body.body, context=context, ticket_prefix=body.ticket_prefix)
    return {
        "plan_name": result.plan_name,
        "tasks": [t.model_dump(mode="json") for t in result.tasks],
    }


@router.post("/batch-extract")
async def batch_extract(
    body: BatchExtractRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Extract tasks from multiple emails at once."""
    try:
        text_parts: list[str] = []
        subjects: list[str] = []

        for message_id in body.message_ids:
            msg = await get_message_body(user.access_token, message_id)
            subjects.append(msg["subject"])
            text_parts.append(
                f"--- Email: {msg['subject']} ---\n{msg['body_text']}"
            )

            if body.include_attachments:
                attachments = await get_message_attachments(
                    user.access_token, message_id
                )
                for att in attachments:
                    try:
                        file_bytes = base64.b64decode(att["content_bytes"])
                        att_text = parse_document(att["name"], file_bytes)
                        text_parts.append(
                            f"--- Attachment: {att['name']} ---\n{att_text}"
                        )
                    except (ValueError, Exception) as exc:
                        logger.warning(
                            "Skipping attachment %s: %s", att["name"], exc
                        )

        combined_text = "\n\n".join(text_parts)
        context = "Emails: " + ", ".join(subjects)

        result = await extract_from_text(
            combined_text, context=context, ticket_prefix=body.ticket_prefix
        )
        return {
            "plan_name": result.plan_name,
            "tasks": [t.model_dump(mode="json") for t in result.tasks],
            "source_count": len(body.message_ids),
            "subjects": subjects,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
