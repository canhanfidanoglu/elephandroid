from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.database import get_db

from src.emails.client import get_message_body
from src.meetings.client import get_transcript_content
from src.teams_chat.client import format_chat_to_text, get_chat_messages

from .engine import approve_tasks, process_message, reject_tasks
from .models import ChatDocument, ChatMessage, ChatSession, PendingTaskSet
from .rag import ingest_document

router = APIRouter(prefix="/chat", tags=["chat"])


# --- Request / Response models ---


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    plan_id: str = ""


class ApproveRequest(BaseModel):
    plan_id: str
    default_bucket_id: str
    auto_create_buckets: bool = True


class ImportTranscriptRequest(BaseModel):
    join_url: str
    meeting_subject: str | None = None


class ImportEmailRequest(BaseModel):
    message_id: str
    email_subject: str | None = None


class ImportChatRequest(BaseModel):
    chat_id: str
    chat_topic: str | None = None


# --- Endpoints ---


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = ChatSession(user_id=user.user_id, title=body.title)
    db.add(session)
    await db.commit()
    return {"id": session.id, "title": session.title, "created_at": str(session.created_at)}


@router.get("/sessions")
async def list_sessions(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": str(s.created_at),
            "updated_at": str(s.updated_at),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    # Verify ownership
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = (await db.execute(msg_stmt)).scalars().all()

    # Also fetch pending task sets for this session
    pts_stmt = select(PendingTaskSet).where(
        PendingTaskSet.session_id == session_id
    )
    pending_sets = (await db.execute(pts_stmt)).scalars().all()
    pending_map = {p.message_id: p for p in pending_sets}

    result = []
    for msg in messages:
        entry = {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "metadata": msg.metadata_json,
            "created_at": str(msg.created_at),
        }
        if msg.id in pending_map:
            p = pending_map[msg.id]
            entry["pending_task_set"] = {
                "id": p.id,
                "status": p.status,
                "tasks_json": p.tasks_json,
            }
        result.append(entry)
    return result


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Verify ownership
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        process_message(
            session_id,
            user.user_id,
            body.content,
            db,
            access_token=user.access_token,
            plan_id=body.plan_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/documents")
async def upload_document(
    session_id: str,
    file: UploadFile,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Verify ownership
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    file_bytes = await file.read()
    filename = file.filename or "upload.txt"

    doc = await ingest_document(filename, file_bytes, session_id=session_id)

    # Persist document record
    db.add(doc)
    await db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "chunk_count": doc.chunk_count,
    }


@router.post("/sessions/{session_id}/tasks/{pending_id}/approve")
async def approve_task_set(
    session_id: str,
    pending_id: str,
    body: ApproveRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Verify session ownership
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await approve_tasks(
            pending_id=pending_id,
            plan_id=body.plan_id,
            default_bucket_id=body.default_bucket_id,
            access_token=user.access_token,
            db=db,
            auto_create_buckets=body.auto_create_buckets,
        )
        return {"status": "synced", "sync_result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions/{session_id}/tasks/{pending_id}/reject")
async def reject_task_set(
    session_id: str,
    pending_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Verify session ownership
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        await reject_tasks(pending_id, db)
        return {"status": "rejected"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions/{session_id}/import-transcript")
async def import_meeting_transcript(
    session_id: str,
    body: ImportTranscriptRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import a Teams meeting transcript into the chat session as a document for RAG."""
    # Verify ownership
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await get_transcript_content(user.access_token, body.join_url)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Ingest transcript as a document into RAG
    subject = body.meeting_subject or "meeting"
    filename = f"transcript-{subject.replace(' ', '-')[:50]}.txt"
    doc = await ingest_document(
        filename, result["content"].encode("utf-8"), session_id=session_id
    )
    db.add(doc)

    # Also save the transcript as a system message for context
    msg = ChatMessage(
        session_id=session_id,
        role="system",
        content=f"Meeting transcript imported: \"{subject}\" ({doc.chunk_count} chunks indexed)",
    )
    db.add(msg)
    await db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "chunk_count": doc.chunk_count,
        "transcript_length": len(result["content"]),
    }


@router.post("/sessions/{session_id}/import-email")
async def import_email(
    session_id: str,
    body: ImportEmailRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import an Outlook email body into the chat session as a document for RAG."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_data = await get_message_body(user.access_token, body.message_id)
    subject = body.email_subject or msg_data["subject"] or "email"
    filename = f"email-{subject.replace(' ', '-')[:50]}.txt"
    text = f"From: {msg_data['from_name']} <{msg_data['from_email']}>\nSubject: {msg_data['subject']}\n\n{msg_data['body_text']}"

    doc = await ingest_document(filename, text.encode("utf-8"), session_id=session_id)
    db.add(doc)

    sys_msg = ChatMessage(
        session_id=session_id,
        role="system",
        content=f"Email imported: \"{subject}\" from {msg_data['from_email']} ({doc.chunk_count} chunks indexed)",
    )
    db.add(sys_msg)
    await db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "chunk_count": doc.chunk_count,
        "email_length": len(text),
    }


@router.post("/sessions/{session_id}/import-chat")
async def import_teams_chat(
    session_id: str,
    body: ImportChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import Teams chat messages into the chat session as a document for RAG."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.user_id
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msgs = await get_chat_messages(user.access_token, body.chat_id)
    if not msgs:
        raise HTTPException(status_code=400, detail="No messages found in this chat.")

    text = format_chat_to_text(msgs)
    topic = body.chat_topic or "teams-chat"
    filename = f"chat-{topic.replace(' ', '-')[:50]}.txt"

    doc = await ingest_document(filename, text.encode("utf-8"), session_id=session_id)
    db.add(doc)

    sys_msg = ChatMessage(
        session_id=session_id,
        role="system",
        content=f"Teams chat imported: \"{topic}\" ({len(msgs)} messages, {doc.chunk_count} chunks indexed)",
    )
    db.add(sys_msg)
    await db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "chunk_count": doc.chunk_count,
        "message_count": len(msgs),
    }
