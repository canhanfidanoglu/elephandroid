from datetime import datetime

from pydantic import BaseModel


class BucketProgress(BaseModel):
    name: str
    total: int
    completed: int
    in_progress: int
    not_started: int


class EpicProgress(BaseModel):
    name: str
    total: int
    completed: int
    percentage: float


class PlanReport(BaseModel):
    plan_name: str
    generated_at: datetime
    total_tasks: int
    completed_tasks: int
    overall_percentage: float
    buckets: list[BucketProgress]
    epics: list[EpicProgress]
