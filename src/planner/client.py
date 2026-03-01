import asyncio
import uuid

import httpx

from .models import BucketInfo, CreateTaskRequest, PlanInfo, TaskInfo

BASE_URL = "https://graph.microsoft.com/v1.0"

MAX_RETRIES = 3


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Send an HTTP request with retry logic for 429 and 5xx responses.

    Reads the Retry-After header on 429 responses.  Uses exponential backoff
    for 5xx responses.  Retries up to ``MAX_RETRIES`` times and raises
    ``httpx.HTTPStatusError`` on final failure.
    """
    for attempt in range(MAX_RETRIES):
        response = await client.request(method, url, **kwargs)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "5"))
            await asyncio.sleep(retry_after)
            continue

        if response.status_code >= 500:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                continue

        response.raise_for_status()
        return response

    # Final attempt already raised via raise_for_status above, but guard
    # against the edge case where the loop exits without returning.
    response.raise_for_status()
    return response


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def resolve_user_id(access_token: str, email_or_name: str) -> str | None:
    """Resolve an email or UPN to an Azure AD user OID."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        try:
            response = await _request_with_retry(
                client,
                "GET",
                f"/users/{email_or_name}",
                headers=_headers(access_token),
            )
            return response.json().get("id")
        except httpx.HTTPStatusError:
            return None


async def list_groups(access_token: str) -> list[dict]:
    """List Microsoft 365 groups the current user is a member of."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await _request_with_retry(
            client,
            "GET",
            "/me/memberOf/microsoft.graph.group",
            headers=_headers(access_token),
        )
        return response.json().get("value", [])


async def list_plans(access_token: str, group_id: str) -> list[PlanInfo]:
    """List Planner plans that belong to a group."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await _request_with_retry(
            client,
            "GET",
            f"/groups/{group_id}/planner/plans",
            headers=_headers(access_token),
        )
        plans = response.json().get("value", [])
        return [
            PlanInfo(id=p["id"], title=p["title"], group_id=group_id)
            for p in plans
        ]


async def list_buckets(access_token: str, plan_id: str) -> list[BucketInfo]:
    """List buckets within a Planner plan."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await _request_with_retry(
            client,
            "GET",
            f"/planner/plans/{plan_id}/buckets",
            headers=_headers(access_token),
        )
        buckets = response.json().get("value", [])
        return [
            BucketInfo(
                id=b["id"],
                name=b["name"],
                plan_id=plan_id,
                order_hint=b.get("orderHint", ""),
            )
            for b in buckets
        ]


async def create_plan(
    access_token: str, group_id: str, title: str
) -> PlanInfo:
    """Create a new Planner plan within a group."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await _request_with_retry(
            client,
            "POST",
            "/planner/plans",
            headers=_headers(access_token),
            json={"owner": group_id, "title": title},
        )
        data = response.json()
        return PlanInfo(id=data["id"], title=data["title"], group_id=group_id)


async def create_bucket(
    access_token: str, plan_id: str, name: str
) -> BucketInfo:
    """Create a new bucket within a Planner plan."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await _request_with_retry(
            client,
            "POST",
            "/planner/buckets",
            headers=_headers(access_token),
            json={"planId": plan_id, "name": name},
        )
        data = response.json()
        return BucketInfo(
            id=data["id"],
            name=data["name"],
            plan_id=plan_id,
            order_hint=data.get("orderHint", ""),
        )


async def set_plan_categories(
    access_token: str, plan_id: str, categories: dict[str, str]
) -> None:
    """Set category labels on a plan's details.

    ``categories`` maps e.g. ``{"category1": "Product Foundation", ...}``.
    Requires GET for @odata.etag then PATCH.
    """
    headers = _headers(access_token)
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        details_resp = await _request_with_retry(
            client, "GET", f"/planner/plans/{plan_id}/details", headers=headers,
        )
        etag = details_resp.json().get("@odata.etag", "")
        patch_headers = {**headers, "If-Match": etag}
        await _request_with_retry(
            client,
            "PATCH",
            f"/planner/plans/{plan_id}/details",
            headers=patch_headers,
            json={"categoryDescriptions": categories},
        )


async def list_tasks(
    access_token: str, plan_id: str
) -> list[TaskInfo]:
    """List all tasks in a plan, following pagination links."""
    headers = _headers(access_token)
    tasks: list[TaskInfo] = []
    url = f"/planner/plans/{plan_id}/tasks"

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        while url:
            response = await _request_with_retry(
                client, "GET", url, headers=headers,
            )
            data = response.json()
            for t in data.get("value", []):
                tasks.append(
                    TaskInfo(
                        id=t["id"],
                        title=t.get("title", ""),
                        bucket_id=t.get("bucketId", ""),
                        percent_complete=t.get("percentComplete", 0),
                        priority=t.get("priority", 5),
                        start_date=t.get("startDateTime"),
                        due_date=t.get("dueDateTime"),
                        applied_categories=t.get("appliedCategories", {}),
                    )
                )
            next_link = data.get("@odata.nextLink")
            url = next_link if next_link else None

    return tasks


async def update_task(
    access_token: str,
    task_id: str,
    *,
    title: str | None = None,
    percent_complete: int | None = None,
    priority: int | None = None,
    due_date: str | None = None,
    start_date: str | None = None,
    bucket_id: str | None = None,
    assignee_ids: list[str] | None = None,
) -> dict:
    """Update a Planner task. Requires GET for @odata.etag then PATCH."""
    headers = _headers(access_token)
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Get current task for etag
        resp = await _request_with_retry(
            client, "GET", f"/planner/tasks/{task_id}", headers=headers,
        )
        etag = resp.json().get("@odata.etag", "")

        patch_body: dict = {}
        if title is not None:
            patch_body["title"] = title
        if percent_complete is not None:
            patch_body["percentComplete"] = percent_complete
        if priority is not None:
            patch_body["priority"] = priority
        if due_date is not None:
            patch_body["dueDateTime"] = due_date
        if start_date is not None:
            patch_body["startDateTime"] = start_date
        if bucket_id is not None:
            patch_body["bucketId"] = bucket_id
        if assignee_ids is not None:
            patch_body["assignments"] = {
                uid: {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "orderHint": " !",
                }
                for uid in assignee_ids
            }

        if not patch_body:
            return resp.json()

        patch_headers = {**headers, "If-Match": etag}
        patch_resp = await _request_with_retry(
            client,
            "PATCH",
            f"/planner/tasks/{task_id}",
            headers=patch_headers,
            json=patch_body,
        )
        return patch_resp.json()


async def delete_task(access_token: str, task_id: str) -> None:
    """Delete a Planner task. Requires GET for @odata.etag then DELETE."""
    headers = _headers(access_token)
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await _request_with_retry(
            client, "GET", f"/planner/tasks/{task_id}", headers=headers,
        )
        etag = resp.json().get("@odata.etag", "")
        delete_headers = {**headers, "If-Match": etag}
        await _request_with_retry(
            client, "DELETE", f"/planner/tasks/{task_id}", headers=delete_headers,
        )


async def create_task(access_token: str, request: CreateTaskRequest) -> str:
    """Create a Planner task with optional description and checklist.

    Three-step process:
      1. POST the task to create it.
      2. If description or checklist items are provided, GET the task details
         to obtain the @odata.etag.
      3. PATCH the task details with the description and/or checklist.

    Returns the created task id.
    """
    headers = _headers(access_token)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Step 1 -- create the task
        task_body: dict = {
            "planId": request.plan_id,
            "bucketId": request.bucket_id,
            "title": request.title,
        }
        if request.priority is not None:
            task_body["priority"] = request.priority
        if request.start_date is not None:
            task_body["startDateTime"] = request.start_date
        if request.due_date is not None:
            task_body["dueDateTime"] = request.due_date
        if request.applied_categories:
            task_body["appliedCategories"] = request.applied_categories
        if request.assignee_ids:
            task_body["assignments"] = {
                uid: {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "orderHint": " !",
                }
                for uid in request.assignee_ids
            }

        create_response = await _request_with_retry(
            client,
            "POST",
            "/planner/tasks",
            headers=headers,
            json=task_body,
        )
        task_data = create_response.json()
        task_id: str = task_data["id"]

        # Step 2 & 3 -- update details if needed
        needs_patch = request.description or request.checklist_items
        if needs_patch:
            details_response = await _request_with_retry(
                client,
                "GET",
                f"/planner/tasks/{task_id}/details",
                headers=headers,
            )
            details_data = details_response.json()
            etag = details_data.get("@odata.etag", "")

            patch_body: dict = {}
            if request.description:
                patch_body["description"] = request.description
            if request.checklist_items:
                checklist: dict = {}
                for item in request.checklist_items:
                    key = str(uuid.uuid4())
                    checklist[key] = {
                        "@odata.type": "microsoft.graph.plannerChecklistItem",
                        "title": item,
                        "isChecked": False,
                    }
                patch_body["checklist"] = checklist

            patch_headers = {**headers, "If-Match": etag}
            await _request_with_retry(
                client,
                "PATCH",
                f"/planner/tasks/{task_id}/details",
                headers=patch_headers,
                json=patch_body,
            )

        return task_id
