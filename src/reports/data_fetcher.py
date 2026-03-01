from collections import defaultdict
from datetime import datetime, timezone

import httpx

from src.planner.client import list_buckets, list_tasks

from .models import BucketProgress, EpicProgress, PlanReport

CATEGORY_EPIC_MAP = {
    "category1": "Product Foundation",
    "category2": "Legal & Compliance",
    "category3": "Technical Architecture",
    "category4": "AI/ML Core",
    "category5": "Go-to-Market",
    "category6": "Operations & Security",
}


async def build_plan_report(access_token: str, plan_id: str) -> PlanReport:
    """Fetch tasks and buckets from Planner and build a PlanReport."""

    # Fetch plan title directly
    async with httpx.AsyncClient(base_url="https://graph.microsoft.com/v1.0") as client:
        resp = await client.get(
            f"/planner/plans/{plan_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        plan_name = resp.json().get("title", "Unknown Plan")

    # Fetch tasks and buckets
    tasks = await list_tasks(access_token, plan_id)
    buckets = await list_buckets(access_token, plan_id)

    bucket_id_to_name = {b.id: b.name for b in buckets}

    # Build bucket progress
    bucket_stats: dict[str, dict] = {}
    for b in buckets:
        bucket_stats[b.id] = {
            "name": b.name,
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "not_started": 0,
        }

    # Build epic progress
    epic_stats: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "completed": 0}
    )

    total_completed = 0

    for task in tasks:
        # Bucket stats
        if task.bucket_id in bucket_stats:
            bucket_stats[task.bucket_id]["total"] += 1
            if task.percent_complete == 100:
                bucket_stats[task.bucket_id]["completed"] += 1
                total_completed += 1
            elif task.percent_complete > 0:
                bucket_stats[task.bucket_id]["in_progress"] += 1
            else:
                bucket_stats[task.bucket_id]["not_started"] += 1
        else:
            # Task in an unknown bucket — still count it
            if task.percent_complete == 100:
                total_completed += 1

        # Epic stats from applied categories
        for cat_key, is_applied in task.applied_categories.items():
            if is_applied and cat_key in CATEGORY_EPIC_MAP:
                epic_name = CATEGORY_EPIC_MAP[cat_key]
                epic_stats[epic_name]["total"] += 1
                if task.percent_complete == 100:
                    epic_stats[epic_name]["completed"] += 1

    total_tasks = len(tasks)
    overall_percentage = (
        (total_completed / total_tasks * 100) if total_tasks > 0 else 0.0
    )

    bucket_progress = [
        BucketProgress(**stats)
        for stats in bucket_stats.values()
    ]

    epic_progress = [
        EpicProgress(
            name=name,
            total=stats["total"],
            completed=stats["completed"],
            percentage=(
                stats["completed"] / stats["total"] * 100
                if stats["total"] > 0
                else 0.0
            ),
        )
        for name, stats in sorted(epic_stats.items())
    ]

    return PlanReport(
        plan_name=plan_name,
        generated_at=datetime.now(timezone.utc),
        total_tasks=total_tasks,
        completed_tasks=total_completed,
        overall_percentage=round(overall_percentage, 1),
        buckets=bucket_progress,
        epics=epic_progress,
    )
