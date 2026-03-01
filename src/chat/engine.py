import json
import logging
from collections.abc import AsyncGenerator
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.task_extractor import _parse_task_item
from src.config import settings
from src.excel.models import ParsedTask
from src.providers import stream_chat
from src.sync.engine import sync_tasks_to_planner

from .actions import (
    get_task_context,
    handle_delete_task,
    handle_list_tasks,
    handle_update_task,
)
from .models import ChatMessage, ChatSession, PendingTaskSet
from src.prompts import CHAT_SYSTEM
from .streaming import extract_json_action

logger = logging.getLogger(__name__)


async def _get_or_create_session(
    session_id: str, user_id: str, db: AsyncSession
) -> ChatSession:
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        session = ChatSession(id=session_id, user_id=user_id)
        db.add(session)
        await db.flush()
    return session


async def _get_history(session_id: str, db: AsyncSession) -> list[dict]:
    """Fetch the last N messages for the session as chat messages."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(settings.chat_max_history)
    )
    rows = (await db.execute(stmt)).scalars().all()
    rows = list(reversed(rows))
    return [{"role": msg.role, "content": msg.content} for msg in rows]


async def process_message(
    session_id: str,
    user_id: str,
    user_message: str,
    db: AsyncSession,
    access_token: str = "",
    plan_id: str = "",
) -> AsyncGenerator[str, None]:
    """Process a user message and stream the assistant response.

    Yields SSE-formatted text chunks. After streaming completes,
    saves messages to DB and handles actions (CRUD, task extraction).
    """
    await _get_or_create_session(session_id, user_id, db)

    # 1. Load history
    history = await _get_history(session_id, db)

    # 2. Build system prompt with task context
    task_context = ""
    if access_token and plan_id:
        try:
            task_context = await get_task_context(access_token, plan_id)
        except Exception as exc:
            logger.warning("Failed to load task context: %s", exc)

    system_prompt = CHAT_SYSTEM.format(
        current_date=date.today().isoformat(),
        task_context=task_context or "No plan selected.",
    )

    # 3. Build messages list
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # 4. Stream response
    full_response = ""
    async for chunk in stream_chat(messages):
        full_response += chunk
        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

    # 5. Save messages to DB
    user_msg = ChatMessage(
        session_id=session_id, role="user", content=user_message
    )
    assistant_msg = ChatMessage(
        session_id=session_id, role="assistant", content=full_response
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.flush()

    # 6. Detect and handle actions
    action = extract_json_action(full_response)
    if action:
        action_type = action.get("action", "")

        if action_type == "extract_tasks":
            async for event in _handle_extract_tasks(
                action, session_id, assistant_msg.id, db
            ):
                yield event

        elif action_type in ("update_task", "delete_task", "list_tasks"):
            if access_token and plan_id:
                result_text = await _dispatch_planner_action(
                    action_type, action, access_token, plan_id
                )
                yield f"data: {json.dumps({'type': 'action_result', 'action': action_type, 'result': result_text})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'action_result', 'action': action_type, 'result': 'No plan selected. Please select a plan to manage tasks.'})}\n\n"

    await db.commit()

    # Update session title from first message
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one()
    if session.title is None:
        session.title = user_message[:100]
        await db.commit()

    yield "data: [DONE]\n\n"


async def _handle_extract_tasks(
    action: dict,
    session_id: str,
    message_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Handle extract_tasks action -- parse tasks and create pending set."""
    raw_tasks = action.get("tasks", [])
    tasks: list[ParsedTask] = []
    for idx, item in enumerate(raw_tasks, start=1):
        try:
            task = _parse_task_item(item, idx, "CHAT")
            tasks.append(task)
        except Exception as exc:
            logger.warning("Skipping malformed chat task %d: %s", idx, exc)

    if tasks:
        pending = PendingTaskSet(
            session_id=session_id,
            message_id=message_id,
            tasks_json=json.dumps(
                [t.model_dump(mode="json") for t in tasks]
            ),
            status="pending",
        )
        db.add(pending)
        await db.flush()

        tasks_data = [t.model_dump(mode="json") for t in tasks]
        yield f"data: {json.dumps({'type': 'tasks', 'pending_id': pending.id, 'tasks': tasks_data})}\n\n"


async def _dispatch_planner_action(
    action_type: str,
    action: dict,
    access_token: str,
    plan_id: str,
) -> str:
    """Dispatch a Planner CRUD action and return the result text."""
    try:
        if action_type == "list_tasks":
            return await handle_list_tasks(access_token, plan_id)
        elif action_type == "update_task":
            return await handle_update_task(access_token, plan_id, action)
        elif action_type == "delete_task":
            return await handle_delete_task(access_token, plan_id, action)
        else:
            return f"Unknown action: {action_type}"
    except Exception as exc:
        logger.error("Planner action '%s' failed: %s", action_type, exc)
        return f"Action failed: {exc}"


async def approve_tasks(
    pending_id: str,
    plan_id: str,
    default_bucket_id: str,
    access_token: str,
    db: AsyncSession,
    auto_create_buckets: bool = True,
) -> dict:
    """Approve a pending task set and sync to Planner."""
    stmt = select(PendingTaskSet).where(PendingTaskSet.id == pending_id)
    pending = (await db.execute(stmt)).scalar_one_or_none()
    if pending is None:
        raise ValueError("Pending task set not found")
    if pending.status != "pending":
        raise ValueError(f"Cannot approve: status is {pending.status}")

    raw_list = json.loads(pending.tasks_json)
    tasks = [ParsedTask(**t) for t in raw_list]

    result = await sync_tasks_to_planner(
        access_token=access_token,
        tasks=tasks,
        plan_id=plan_id,
        default_bucket_id=default_bucket_id,
        auto_create_buckets=auto_create_buckets,
    )

    pending.status = "synced"
    pending.plan_id = plan_id
    pending.resolved_at = datetime.utcnow()
    await db.commit()

    return result.to_dict()


async def reject_tasks(pending_id: str, db: AsyncSession) -> None:
    """Reject a pending task set."""
    stmt = select(PendingTaskSet).where(PendingTaskSet.id == pending_id)
    pending = (await db.execute(stmt)).scalar_one_or_none()
    if pending is None:
        raise ValueError("Pending task set not found")
    if pending.status != "pending":
        raise ValueError(f"Cannot reject: status is {pending.status}")

    pending.status = "rejected"
    pending.resolved_at = datetime.utcnow()
    await db.commit()
