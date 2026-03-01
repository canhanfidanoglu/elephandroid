from pydantic import BaseModel


class PlanInfo(BaseModel):
    id: str
    title: str
    group_id: str


class BucketInfo(BaseModel):
    id: str
    name: str
    plan_id: str
    order_hint: str


class ChecklistItem(BaseModel):
    title: str
    is_checked: bool = False


class TaskInfo(BaseModel):
    id: str
    title: str
    bucket_id: str
    percent_complete: int = 0
    priority: int = 5
    start_date: str | None = None
    due_date: str | None = None
    applied_categories: dict[str, bool] = {}


class CreateTaskRequest(BaseModel):
    plan_id: str
    bucket_id: str
    title: str
    description: str | None = None
    priority: int | None = None  # 1=urgent, 3=high, 5=medium, 9=low
    start_date: str | None = None  # ISO 8601
    due_date: str | None = None  # ISO 8601
    checklist_items: list[str] = []
    applied_categories: dict[str, bool] = {}  # e.g. {"category1": True}
    assignee_ids: list[str] = []  # Azure AD user OIDs
