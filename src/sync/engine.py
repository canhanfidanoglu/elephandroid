import asyncio
import logging

from src.excel.models import ColumnMapping, ParsedTask
from src.excel.parser import parse_excel
from src.planner.client import (
    create_bucket,
    create_task,
    list_buckets,
    resolve_user_id,
)
from src.planner.models import CreateTaskRequest

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 3

# Epic → Planner category mapping (set on plan details)
EPIC_CATEGORY_MAP = {
    "product foundation": "category1",
    "legal & compliance": "category2",
    "technical architecture": "category3",
    "ai/ml core": "category4",
    "go-to-market": "category5",
    "operations & security": "category6",
}


class SyncResult:
    def __init__(self):
        self.total_rows: int = 0
        self.tasks_created: int = 0
        self.tasks_failed: int = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "tasks_created": self.tasks_created,
            "tasks_failed": self.tasks_failed,
            "errors": self.errors,
        }


async def _resolve_bucket_map(
    access_token: str, plan_id: str
) -> dict[str, str]:
    buckets = await list_buckets(access_token, plan_id)
    return {b.name.lower(): b.id for b in buckets}


def _resolve_categories(epic: str | None) -> dict[str, bool]:
    if not epic:
        return {}
    category = EPIC_CATEGORY_MAP.get(epic.lower())
    if category:
        return {category: True}
    return {}


async def _create_single_task(
    access_token: str,
    task: ParsedTask,
    plan_id: str,
    bucket_id: str,
    semaphore: asyncio.Semaphore,
    result: SyncResult,
    assignee_ids: list[str] | None = None,
) -> None:
    async with semaphore:
        try:
            title = f"{task.ticket_id} {task.title}"

            # Build description from Notes column
            description = task.description  # None if no notes

            req = CreateTaskRequest(
                plan_id=plan_id,
                bucket_id=bucket_id,
                title=title,
                description=description,
                priority=task.priority,
                start_date=task.start_date.isoformat() if task.start_date else None,
                due_date=task.due_date.isoformat() if task.due_date else None,
                checklist_items=task.checklist_items,
                applied_categories=_resolve_categories(task.epic),
                assignee_ids=assignee_ids or [],
            )
            await create_task(access_token, req)
            result.tasks_created += 1
        except Exception as exc:
            result.tasks_failed += 1
            msg = f"Failed to create task '{task.ticket_id} {task.title}': {exc}"
            result.errors.append(msg)
            logger.warning(msg)


async def _resolve_assignee_map(
    access_token: str, tasks: list[ParsedTask]
) -> dict[str, str]:
    """Build a cache of assignee email/name → Azure AD OID."""
    unique_assignees = {
        t.assignee.lower()
        for t in tasks
        if t.assignee
    }
    assignee_map: dict[str, str] = {}
    for assignee in unique_assignees:
        oid = await resolve_user_id(access_token, assignee)
        if oid:
            assignee_map[assignee] = oid
    return assignee_map


async def sync_tasks_to_planner(
    access_token: str,
    tasks: list[ParsedTask],
    plan_id: str,
    default_bucket_id: str,
    auto_create_buckets: bool = False,
) -> SyncResult:
    """Sync a list of ParsedTask objects to Planner.

    If *auto_create_buckets* is True, any bucket names found in the tasks
    that do not yet exist in the plan will be created automatically.
    """
    result = SyncResult()
    result.total_rows = len(tasks)

    if not tasks:
        return result

    # Resolve existing bucket names to IDs
    bucket_map = await _resolve_bucket_map(access_token, plan_id)

    # Auto-create missing buckets
    if auto_create_buckets:
        needed = {
            t.bucket_name
            for t in tasks
            if t.bucket_name and t.bucket_name.lower() not in bucket_map
        }
        for name in needed:
            try:
                bucket = await create_bucket(access_token, plan_id, name)
                bucket_map[bucket.name.lower()] = bucket.id
            except Exception as exc:
                logger.warning("Failed to auto-create bucket '%s': %s", name, exc)

    # Resolve assignee names/emails to Azure AD OIDs
    assignee_map = await _resolve_assignee_map(access_token, tasks)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    coros = []
    for task in tasks:
        bucket_id = default_bucket_id
        if task.bucket_name:
            bucket_id = bucket_map.get(
                task.bucket_name.lower(), default_bucket_id
            )

        # Resolve assignee
        assignee_ids = []
        if task.assignee:
            oid = assignee_map.get(task.assignee.lower())
            if oid:
                assignee_ids.append(oid)

        coros.append(
            _create_single_task(
                access_token, task, plan_id, bucket_id, semaphore, result,
                assignee_ids=assignee_ids,
            )
        )

    await asyncio.gather(*coros)
    return result


async def sync_excel_to_planner(
    access_token: str,
    file_bytes: bytes,
    plan_id: str,
    default_bucket_id: str,
    mapping: ColumnMapping | None = None,
) -> SyncResult:
    if mapping is None:
        mapping = ColumnMapping()

    tasks = parse_excel(file_bytes, mapping)
    return await sync_tasks_to_planner(
        access_token=access_token,
        tasks=tasks,
        plan_id=plan_id,
        default_bucket_id=default_bucket_id,
        auto_create_buckets=False,
    )
