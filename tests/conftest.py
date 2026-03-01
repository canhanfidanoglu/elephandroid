"""Shared test fixtures."""

from datetime import date

import pytest

from src.excel.models import ParsedTask
from src.planner.models import BucketInfo, TaskInfo


@pytest.fixture
def make_task():
    """Factory to create ParsedTask instances with sane defaults."""

    def _make(
        ticket_id: str = "T-001",
        title: str = "Test task",
        epic: str | None = None,
        bucket_name: str | None = None,
        priority: int | None = 5,
        assignee: str | None = None,
        due_date: date | None = None,
        checklist_items: list[str] | None = None,
    ) -> ParsedTask:
        return ParsedTask(
            ticket_id=ticket_id,
            title=title,
            epic=epic,
            bucket_name=bucket_name,
            priority=priority,
            assignee=assignee,
            due_date=due_date,
            checklist_items=checklist_items or [],
        )

    return _make


@pytest.fixture
def make_task_info():
    """Factory to create TaskInfo (Planner API model) instances."""

    def _make(
        id: str = "task-1",
        title: str = "Test task",
        bucket_id: str = "bucket-1",
        percent_complete: int = 0,
        priority: int = 5,
        due_date: str | None = None,
        applied_categories: dict[str, bool] | None = None,
    ) -> TaskInfo:
        return TaskInfo(
            id=id,
            title=title,
            bucket_id=bucket_id,
            percent_complete=percent_complete,
            priority=priority,
            due_date=due_date,
            applied_categories=applied_categories or {},
        )

    return _make


@pytest.fixture
def make_bucket():
    """Factory to create BucketInfo instances."""

    def _make(
        id: str = "bucket-1",
        name: str = "To Do",
        plan_id: str = "plan-1",
        order_hint: str = "",
    ) -> BucketInfo:
        return BucketInfo(
            id=id,
            name=name,
            plan_id=plan_id,
            order_hint=order_hint,
        )

    return _make
