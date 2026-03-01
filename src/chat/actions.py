"""Dispatch LLM actions to Planner API calls."""

import logging

from src.planner.client import (
    delete_task,
    list_buckets,
    list_tasks,
    resolve_user_id,
    update_task,
)
from src.planner.models import BucketInfo, TaskInfo

logger = logging.getLogger(__name__)

# Status text → percent_complete
_STATUS_MAP = {
    "completed": 100, "done": 100, "finished": 100, "complete": 100,
    "in progress": 50, "started": 50, "working": 50, "active": 50,
    "not started": 0, "reopen": 0, "todo": 0, "pending": 0,
}

_PRIORITY_LABELS = {1: "Urgent", 3: "Important", 5: "Medium", 9: "Low"}


def _find_task_by_title(tasks: list[TaskInfo], query: str) -> TaskInfo | None:
    """Find a task by exact or partial title match (case-insensitive)."""
    query_lower = query.lower().strip()
    # Exact match first
    for t in tasks:
        if t.title.lower() == query_lower:
            return t
    # Partial match
    for t in tasks:
        if query_lower in t.title.lower():
            return t
    return None


def _format_task_list(
    tasks: list[TaskInfo],
    buckets: list[BucketInfo],
) -> str:
    """Format tasks as a readable summary for the LLM/user."""
    if not tasks:
        return "No tasks found in this plan."

    bucket_map = {b.id: b.name for b in buckets}
    lines = []

    # Group by bucket
    by_bucket: dict[str, list[TaskInfo]] = {}
    for t in tasks:
        bname = bucket_map.get(t.bucket_id, "Unknown")
        by_bucket.setdefault(bname, []).append(t)

    for bucket_name, bucket_tasks in by_bucket.items():
        lines.append(f"\n**{bucket_name}** ({len(bucket_tasks)} tasks)")
        for t in bucket_tasks:
            status = "Done" if t.percent_complete == 100 else (
                "In Progress" if t.percent_complete == 50 else "Not Started"
            )
            priority = _PRIORITY_LABELS.get(t.priority, "Medium")
            due = f", due {t.due_date[:10]}" if t.due_date else ""
            lines.append(f"  - [{status}] {t.title} (priority: {priority}{due})")

    total = len(tasks)
    done = sum(1 for t in tasks if t.percent_complete == 100)
    in_progress = sum(1 for t in tasks if t.percent_complete == 50)
    lines.insert(0, f"**{total} tasks** ({done} done, {in_progress} in progress, {total - done - in_progress} not started)")

    return "\n".join(lines)


async def handle_list_tasks(
    access_token: str,
    plan_id: str,
) -> str:
    """List all tasks and return formatted text."""
    tasks = await list_tasks(access_token, plan_id)
    buckets = await list_buckets(access_token, plan_id)
    return _format_task_list(tasks, buckets)


async def handle_update_task(
    access_token: str,
    plan_id: str,
    action: dict,
) -> str:
    """Update a task based on the LLM action dict."""
    task_title = action.get("task_title", "")
    updates = action.get("updates", {})

    tasks = await list_tasks(access_token, plan_id)
    task = _find_task_by_title(tasks, task_title)
    if not task:
        return f"Could not find a task matching '{task_title}'. Please check the task name."

    kwargs: dict = {}

    if "percent_complete" in updates:
        kwargs["percent_complete"] = updates["percent_complete"]

    if "priority" in updates:
        kwargs["priority"] = updates["priority"]

    if "title" in updates:
        kwargs["title"] = updates["title"]

    if "due_date" in updates:
        due = updates["due_date"]
        kwargs["due_date"] = f"{due}T00:00:00Z" if due and "T" not in due else due

    if "start_date" in updates:
        sd = updates["start_date"]
        kwargs["start_date"] = f"{sd}T00:00:00Z" if sd and "T" not in sd else sd

    if "assignee" in updates and updates["assignee"]:
        user_id = await resolve_user_id(access_token, updates["assignee"])
        if user_id:
            kwargs["assignee_ids"] = [user_id]
        else:
            return f"Could not resolve user '{updates['assignee']}'. Please use their email address."

    if "bucket_name" in updates:
        buckets = await list_buckets(access_token, plan_id)
        target_name = updates["bucket_name"].lower()
        bucket = next((b for b in buckets if b.name.lower() == target_name), None)
        if bucket:
            kwargs["bucket_id"] = bucket.id
        else:
            return f"Bucket '{updates['bucket_name']}' not found."

    if not kwargs:
        return "No changes specified."

    await update_task(access_token, task.id, **kwargs)

    # Build confirmation message
    parts = []
    if "percent_complete" in kwargs:
        pc = kwargs["percent_complete"]
        status = "completed" if pc == 100 else ("in progress" if pc == 50 else "not started")
        parts.append(f"status → {status}")
    if "priority" in kwargs:
        parts.append(f"priority → {_PRIORITY_LABELS.get(kwargs['priority'], str(kwargs['priority']))}")
    if "assignee_ids" in kwargs:
        parts.append(f"assigned to {updates['assignee']}")
    if "due_date" in kwargs:
        parts.append(f"due date → {updates['due_date']}")
    if "bucket_id" in kwargs:
        parts.append(f"moved to {updates['bucket_name']}")
    if "title" in kwargs:
        parts.append(f"renamed to '{kwargs['title']}'")

    return f"Updated **{task.title}**: {', '.join(parts)}."


async def handle_delete_task(
    access_token: str,
    plan_id: str,
    action: dict,
) -> str:
    """Delete a task based on the LLM action dict."""
    task_title = action.get("task_title", "")

    tasks = await list_tasks(access_token, plan_id)
    task = _find_task_by_title(tasks, task_title)
    if not task:
        return f"Could not find a task matching '{task_title}'."

    await delete_task(access_token, task.id)
    return f"Deleted task: **{task.title}**."


async def get_task_context(access_token: str, plan_id: str) -> str:
    """Build a compact task context string for the system prompt."""
    try:
        tasks = await list_tasks(access_token, plan_id)
        buckets = await list_buckets(access_token, plan_id)
    except Exception:
        return "No plan context available."

    if not tasks:
        return "Plan is empty — no tasks yet."

    bucket_map = {b.id: b.name for b in buckets}
    lines = []
    for t in tasks:
        status = "DONE" if t.percent_complete == 100 else (
            "WIP" if t.percent_complete == 50 else "TODO"
        )
        bname = bucket_map.get(t.bucket_id, "?")
        lines.append(f"[{status}] {t.title} | bucket: {bname} | priority: {t.priority}")

    return "\n".join(lines)
